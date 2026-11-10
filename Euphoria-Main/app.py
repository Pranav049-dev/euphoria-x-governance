import os
from datetime import datetime, timezone
from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy


def utc_now():
    return datetime.now(timezone.utc)

app = Flask(__name__)
raw_db_url = os.getenv('DATABASE_URL', 'sqlite:///euphoria_x.db')
if raw_db_url.startswith('postgres://'):
    raw_db_url = raw_db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = raw_db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JSON_SORT_KEYS'] = False

db = SQLAlchemy(app)


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, default='Euphoria X Demo')
    content = db.Column(db.Text, nullable=False, default='')
    content_format = db.Column(db.String(40), nullable=False, default='Social post')
    status = db.Column(db.String(30), nullable=False, default='Draft')
    text_colour = db.Column(db.String(7), nullable=False, default='#8a8a8a')
    background = db.Column(db.String(7), nullable=False, default='#ffffff')
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class Revision(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    open_findings = db.Column(db.Integer, nullable=False, default=0)
    high_findings = db.Column(db.Integer, nullable=False, default=0)
    submitted_by = db.Column(db.String(60), nullable=False, default='Creator')
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False, index=True)
    author_role = db.Column(db.String(60), nullable=False, default='Creator')
    event_type = db.Column(db.String(30), nullable=False, default='comment')
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


def iso(value):
    return value.isoformat() if value else None


def get_project():
    project = Project.query.order_by(Project.id.asc()).first()
    if project is None:
        project = Project(name='Euphoria X Demo', content='')
        db.session.add(project)
        db.session.commit()
    return project


def project_payload(project):
    revisions = Revision.query.filter_by(project_id=project.id).order_by(Revision.version.desc()).all()
    activities = Activity.query.filter_by(project_id=project.id).order_by(Activity.created_at.desc()).all()
    return {
        'id': project.id,
        'name': project.name,
        'content': project.content,
        'format': project.content_format,
        'status': project.status,
        'textColour': project.text_colour,
        'background': project.background,
        'createdAt': iso(project.created_at),
        'updatedAt': iso(project.updated_at),
        'revisions': [{
            'id': r.id, 'version': r.version, 'content': r.content,
            'openFindings': r.open_findings, 'highFindings': r.high_findings,
            'by': r.submitted_by, 'time': iso(r.created_at)
        } for r in revisions],
        'activities': [{
            'id': a.id, 'by': a.author_role, 'type': a.event_type,
            'text': a.message, 'time': iso(a.created_at)
        } for a in activities]
    }


@app.get('/')
def home():
    return render_template('index.html')


@app.get('/api/health')
def health():
    return jsonify({'ok': True, 'service': 'Euphoria X API'})


@app.get('/api/project')
def read_project():
    return jsonify(project_payload(get_project()))


@app.put('/api/project')
def update_project():
    data = request.get_json(silent=True) or {}
    project = get_project()
    allowed = {
        'content': ('content', str),
        'format': ('content_format', str),
        'status': ('status', str),
        'textColour': ('text_colour', str),
        'background': ('background', str),
    }
    for key, (attribute, expected_type) in allowed.items():
        if key in data:
            value = data[key]
            if not isinstance(value, expected_type):
                return jsonify({'error': f'{key} must be a string'}), 400
            setattr(project, attribute, value)
    db.session.commit()
    return jsonify(project_payload(project))


@app.post('/api/project/revisions')
def create_revision():
    data = request.get_json(silent=True) or {}
    project = get_project()
    content = data.get('content', project.content)
    role = data.get('by', 'Creator')
    if not isinstance(content, str) or not isinstance(role, str):
        return jsonify({'error': 'content and by must be strings'}), 400
    open_findings = data.get('openFindings', 0)
    high_findings = data.get('highFindings', 0)
    if not isinstance(open_findings, int) or not isinstance(high_findings, int) or min(open_findings, high_findings) < 0:
        return jsonify({'error': 'finding counts must be non-negative integers'}), 400
    last_version = db.session.query(db.func.max(Revision.version)).filter_by(project_id=project.id).scalar() or 0
    revision = Revision(project_id=project.id, version=last_version + 1, content=content,
                        open_findings=open_findings, high_findings=high_findings, submitted_by=role)
    project.content = content
    project.status = 'In review'
    db.session.add(revision)
    db.session.add(Activity(project_id=project.id, author_role=role, event_type='submitted', message=f'Submitted version {revision.version} for review'))
    db.session.commit()
    return jsonify(project_payload(project)), 201


@app.post('/api/project/activities')
def add_activity():
    data = request.get_json(silent=True) or {}
    role = data.get('by', 'Creator')
    event_type = data.get('type', 'comment')
    message = data.get('text', '')
    if not all(isinstance(v, str) for v in (role, event_type, message)) or not message.strip():
        return jsonify({'error': 'by, type and a non-empty text are required'}), 400
    project = get_project()
    db.session.add(Activity(project_id=project.id, author_role=role, event_type=event_type, message=message.strip()))
    db.session.commit()
    return jsonify(project_payload(project)), 201


@app.post('/api/project/decision')
def record_decision():
    data = request.get_json(silent=True) or {}
    decision = data.get('decision')
    role = data.get('by', 'Creator')
    high_findings = data.get('highFindings', 0)
    if decision not in ('Approved', 'Changes requested') or not isinstance(role, str):
        return jsonify({'error': 'Invalid decision or role'}), 400
    if not isinstance(high_findings, int) or high_findings < 0:
        return jsonify({'error': 'highFindings must be a non-negative integer'}), 400
    if decision == 'Approved' and high_findings > 0 and role != 'Authorised reviewer':
        return jsonify({'error': 'Only an Authorised reviewer can approve while high-severity findings remain'}), 403
    project = get_project()
    project.status = decision
    db.session.add(Activity(project_id=project.id, author_role=role, event_type='decision', message=decision))
    db.session.commit()
    return jsonify(project_payload(project))


@app.post('/api/project/restore/<int:revision_id>')
def restore_revision(revision_id):
    project = get_project()
    revision = Revision.query.filter_by(id=revision_id, project_id=project.id).first_or_404()
    project.content = revision.content
    project.status = 'Draft'
    db.session.add(Activity(project_id=project.id, author_role='System', event_type='restored', message=f'Restored version {revision.version}'))
    db.session.commit()
    return jsonify(project_payload(project))


with app.app_context():
    db.create_all()
    get_project()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.getenv('PORT', '5000')), debug=True)
