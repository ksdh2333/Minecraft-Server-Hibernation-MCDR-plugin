#!/usr/bin/env python3
import re
import json

# Read the plugin.json file
with open('plugin/mcdreforged.plugin.json', 'r', encoding='utf-8') as f:
    content = f.read()

# Parse JSON
data = json.loads(content)
current_version = data['version']

# Check if version contains build.X pattern
match = re.search(r'(build\.)(\d+)', current_version)
if match:
    build_prefix = match.group(1)
    build_number = int(match.group(2))
    new_build_number = build_number + 1
    new_version = current_version.replace(f'{build_prefix}{build_number}', f'{build_prefix}{new_build_number}')
    
    # Update the version
    data['version'] = new_version
    
    # Write back to file
    with open('plugin/mcdreforged.plugin.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    
    print(f'Updated version to: {new_version}')
else:
    print('No build.X pattern found in version, skipping update')