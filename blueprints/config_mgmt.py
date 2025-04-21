from flask import Blueprint, jsonify, request
# Import load_configs, save_configs ngay bên trong các function sử dụng để tránh circular import

config_bp = Blueprint('config', __name__, url_prefix='/api/config', template_folder='../templates')

@config_bp.route('/get-configs', methods=['GET'])
def get_configs():
    from app import load_configs
    configs = load_configs()
    return jsonify({'status': 'success', 'configs': list(configs.keys())})

@config_bp.route('/save-config', methods=['POST'])
def save_config():
    from app import load_configs, save_configs
    try:
        data = request.get_json()
        if not data: return jsonify({'status': 'error', 'message': 'Invalid request: No data.'}), 400
        config_name = data.get('config_name')
        config_data = data.get('config_data')
        if not config_name or not config_data:
            return jsonify({'status': 'error', 'message': 'Missing configuration name or data.'}), 400
        if not isinstance(config_data.get('reports'), list):
            return jsonify({'status': 'error', 'message': 'Invalid config data: "reports" must be a list.'}), 400
        configs = load_configs()
        configs[config_name] = config_data
        save_configs(configs)
        return jsonify({'status': 'success', 'message': f'Configuration "{config_name}" saved.'})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'Internal error saving configuration: {e}'}), 500

@config_bp.route('/load-config/<config_name>', methods=['GET'])
def load_config(config_name):
    from app import load_configs
    configs = load_configs()
    config_data = configs.get(config_name)
    if config_data:
        return jsonify({'status': 'success', 'config_data': config_data})
    else:
        return jsonify({'status': 'error', 'message': f'Configuration "{config_name}" not found.'}), 404

@config_bp.route('/delete-config/<config_name>', methods=['DELETE'])
def delete_config(config_name):
    from app import load_configs, save_configs
    configs = load_configs()
    if config_name in configs:
        del configs[config_name]
        save_configs(configs)
        return jsonify({'status': 'success', 'message': f'Configuration "{config_name}" deleted.'})
    else:
        return jsonify({'status': 'error', 'message': f'Configuration "{config_name}" not found.'}), 404
