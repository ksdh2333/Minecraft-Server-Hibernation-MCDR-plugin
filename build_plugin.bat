@echo off
python update_version.py
mcdreforged pack -i plugin/ -o build/ -n {id}-{version}.mcdr