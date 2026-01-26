#!/usr/bin/env python3

from jinja2 import Environment, FileSystemLoader
import os
from pathlib import Path

# project directory
projectDir = Path(os.getcwd())
 
# loading the environment
env = Environment(loader = FileSystemLoader(projectDir / 'jinja2'))
 
# loading the template
template = env.get_template('index.html')
 
# rendering the template and storing the resultant text in variable output
output = template.render()

# write output to 'templates/index.html'
with open(projectDir / 'templates' / 'index.html', 'w') as file:
    file.write(output)

for file in ['disclaimer.html', 'license.html']:
    with open(projectDir / 'jinja2' / file, 'r') as in_file:
        source = in_file.read()
        
        with open(projectDir / 'templates' / file, 'w') as out_file:
            out_file.write(source)
