"""
CamFu AI Engine - Main Application Entry Point
Intelligent surveillance system with priority-based feed ranking
"""

import os
import sys
import yaml
import datetime
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, jsonify
from flask_cors import CORS
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def load_config():
    """Load configuration from YAML file"""
    config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
    if config_path.exists():
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    return {}


def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)
    CORS(app)

    config = load_config()
    app.config['AI_CONFIG'] = config

    from core.engine import CamFuEngine
    ai_engine = CamFuEngine(config)
    ai_engine.start()

    # ── Root dashboard ────────────────────────────────────────────────────────
    @app.route('/', methods=['GET'])
    def dashboard():
        """Live HTML dashboard showing all camera scores"""
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        processors = ai_engine.processors

        rows = ""
        cameras_sorted = sorted(
            processors.items(),
            key=lambda x: x[1].get_scores()['overall'],
            reverse=True
        )

        for cid, proc in cameras_sorted:
            scores = proc.get_scores()
            cam_name = proc.camera_info.get('camera_name', f'Camera {cid}')
            location = proc.camera_info.get('location', 'Unknown')
            overall = scores['overall']
            motion = scores['motion']
            crowd = scores['crowd']
            behavior = scores['behavior']

            # Determine alert level
            if behavior > 0.5:
                row_color = "#3b0a0a"
                badge = '<span style="background:#ef4444;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold;">🔴 ALERT</span>'
            elif overall > 0.5:
                row_color = "#1a2a0a"
                badge = '<span style="background:#f59e0b;color:#000;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold;">⭐ PRIORITY</span>'
            elif overall < 0.2:
                row_color = "#0f1117"
                badge = '<span style="color:#555;font-size:11px;">— IDLE</span>'
            else:
                row_color = "#1a1f2e"
                badge = '<span style="color:#6b7280;font-size:11px;">● NORMAL</span>'

            def bar(val, color):
                pct = int(val * 100)
                return (f'<div style="display:flex;align-items:center;gap:6px">'
                        f'<div style="background:#374151;border-radius:4px;width:100px;height:8px;">'
                        f'<div style="background:{color};width:{pct}px;height:8px;border-radius:4px;max-width:100px;"></div>'
                        f'</div>'
                        f'<span style="font-size:12px;color:#d1d5db;">{val:.2f}</span>'
                        f'</div>')

            rows += f"""
            <tr style="background:{row_color};border-bottom:1px solid #374151;">
              <td style="padding:12px 16px;">
                <div style="font-weight:600;color:#f3f4f6;">📷 {cam_name}</div>
                <div style="font-size:11px;color:#9ca3af;">{location}</div>
              </td>
              <td style="padding:12px 16px;">{bar(motion, '#3b82f6')}</td>
              <td style="padding:12px 16px;">{bar(crowd, '#8b5cf6')}</td>
              <td style="padding:12px 16px;">{bar(behavior, '#ef4444')}</td>
              <td style="padding:12px 16px;">
                {bar(overall, '#10b981')}
              </td>
              <td style="padding:12px 16px;">{badge}</td>
            </tr>"""

        if not rows:
            rows = '<tr><td colspan="6" style="padding:24px;text-align:center;color:#6b7280;">No cameras active yet — waiting for AI engine sync...</td></tr>'

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="3">
  <title>CamFu AI Engine — Live Dashboard</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f1117; color: #f3f4f6; font-family: 'Segoe UI', system-ui, sans-serif; }}
    header {{ background: #111827; border-bottom: 1px solid #374151; padding: 16px 32px; display:flex; align-items:center; justify-content:space-between; }}
    h1 {{ font-size: 20px; font-weight: 700; color: #f9fafb; }}
    .subtitle {{ font-size: 12px; color: #6b7280; margin-top: 2px; }}
    .badge-pill {{ background:#1f2937; border:1px solid #374151; border-radius:999px; padding:4px 12px; font-size:12px; color:#9ca3af; }}
    table {{ width: 100%; border-collapse: collapse; }}
    thead th {{ background: #1f2937; padding: 10px 16px; text-align:left; font-size:12px; font-weight:600; color:#9ca3af; text-transform:uppercase; letter-spacing:.05em; border-bottom:1px solid #374151; }}
    .container {{ padding: 24px 32px; }}
    .meta {{ display:flex; gap:16px; margin-bottom:20px; flex-wrap:wrap; }}
    .stat-card {{ background:#1f2937; border:1px solid #374151; border-radius:8px; padding:12px 20px; }}
    .stat-label {{ font-size:11px; color:#9ca3af; text-transform:uppercase; letter-spacing:.05em; }}
    .stat-value {{ font-size:22px; font-weight:700; color:#f9fafb; margin-top:2px; }}
    .table-wrap {{ background:#1f2937; border:1px solid #374151; border-radius:10px; overflow:hidden; }}
    .refresh-note {{ font-size:11px; color:#6b7280; margin-top:12px; text-align:right; }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>🎥 CamFu AI Engine</h1>
      <div class="subtitle">Intelligent Surveillance — Live Priority Dashboard</div>
    </div>
    <span class="badge-pill">🟢 Engine Online &nbsp;·&nbsp; {now}</span>
  </header>
  <div class="container">
    <div class="meta">
      <div class="stat-card">
        <div class="stat-label">Active Cameras</div>
        <div class="stat-value">{len(processors)}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">🔴 Alerts</div>
        <div class="stat-value" style="color:#ef4444">
          {sum(1 for p in processors.values() if p.get_scores()['behavior'] > 0.5)}
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-label">⭐ High Priority</div>
        <div class="stat-value" style="color:#f59e0b">
          {sum(1 for p in processors.values() if p.get_scores()['overall'] > 0.5)}
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-label">AI Engine Version</div>
        <div class="stat-value" style="font-size:16px">{config.get('app', {}).get('version', '1.0.0')}</div>
      </div>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Camera</th>
            <th>Motion</th>
            <th>Crowd</th>
            <th>Behavior</th>
            <th>Priority Score</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <div class="refresh-note">⟳ Auto-refreshes every 3 seconds</div>
  </div>
</body>
</html>"""
        return html, 200

    # ── Health check ──────────────────────────────────────────────────────────
    @app.route('/health', methods=['GET'])
    def health_check():
        return jsonify({
            'status': 'healthy',
            'service': 'CamFu AI Engine',
            'version': config.get('app', {}).get('version', '1.0.0'),
            'cameras_active': len(ai_engine.processors)
        }), 200

    # ── Live scores API ───────────────────────────────────────────────────────
    @app.route('/api/scores', methods=['GET'])
    def get_scores():
        """Return live scores for all cameras as JSON"""
        result = []
        for cid, proc in ai_engine.processors.items():
            scores = proc.get_scores()
            result.append({
                'camera_id': cid,
                'camera_name': proc.camera_info.get('camera_name', f'Camera {cid}'),
                'location': proc.camera_info.get('location', 'Unknown'),
                **scores
            })
        result.sort(key=lambda x: x['overall'], reverse=True)
        return jsonify(result), 200

    return app


def main():
    """Main entry point"""
    app = create_app()
    config = app.config['AI_CONFIG']

    server_config = config.get('server', {})
    host = server_config.get('host', '0.0.0.0')
    port = server_config.get('port', 5000)

    print(f"Starting CamFu AI Engine on {host}:{port}")
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()
