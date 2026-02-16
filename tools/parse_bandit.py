import json

try:
    with open('bandit-report.json', 'r') as f:
        data = json.load(f)
    
    results = data.get('results', [])
    filtered = [r for r in results if r['issue_severity'] in ['MEDIUM', 'HIGH']]
    
    with open('bandit_issues.txt', 'w', encoding='utf-8') as f:
        f.write(f"Found {len(filtered)} medium/high severity issues:\n")
        for r in filtered:
            f.write(f"{r['filename']}:{r['line_number']} - {r['issue_text']} ({r['test_id']})\n")

except Exception as e:
    with open('bandit_issues.txt', 'w', encoding='utf-8') as f:
        f.write(f"Error parsing report: {e}\n")
