from flask import Blueprint, render_template

public_bp = Blueprint('public', __name__, url_prefix='/public')

@public_bp.route('/')
def index():
    return render_template('public/index.html')

@public_bp.route('/about')
def about():
    return render_template('public/about.html')

@public_bp.route('/clients')
def clients():
    return render_template('public/clients.html')

@public_bp.route('/produccion')
def production():
    return render_template('public/produccion.html')
