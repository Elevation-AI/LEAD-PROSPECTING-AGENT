"""
Shared state between app.py and Agent blueprints.
Avoids the __main__ vs 'app' module duplication issue.
"""

session_data = {}