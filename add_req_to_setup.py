# generate_install_requires.py
import re

file_req = 'requirements.txt'
file_setup = 'setup.py'


requirements = []
with open(file_req, 'r') as f:
    for line in f:
        # 忽略空行和注释
        if line.startswith("-"):
            continue
        if line.strip() and not line.startswith('#'):
            requirements.append(line.strip())

install_requires_str = ",\n        ".join(f"'{req}'" for req in requirements)

with open(file_setup, 'r') as file:
    setup_content = file.read()

# 替换install_requires部分
new_setup_content = re.sub(
    r"(install_requires=\[).*?(\])",
    fr"\1\n        {install_requires_str},\n    \2",
    setup_content,
    flags=re.S
)

with open(file_setup, 'w') as file:
    file.write(new_setup_content)
