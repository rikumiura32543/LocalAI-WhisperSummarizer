#!/usr/bin/env python3
"""
Script to add file_hash and mime_type to all TranscriptionJob instances in test_models.py
"""
import re

# Read the file
with open('/Users/bl32543/Git/m4a_transcribe/tests/unit/test_models.py', 'r') as f:
    content = f.read()

# Pattern to find TranscriptionJob with file_size but missing file_hash
# We'll add file_hash and mime_type after file_size
pattern = r'(TranscriptionJob\([^)]*file_size=\d+,)(\s+)(usage_type_code="meeting",)'

replacement = r'\1\2file_hash="abc123def456",\2mime_type="audio/m4a",\2\3'

# Apply the replacement
new_content = re.sub(pattern, replacement, content)

# Write back
with open('/Users/bl32543/Git/m4a_transcribe/tests/unit/test_models.py', 'w') as f:
    f.write(new_content)

print("✅ Successfully added file_hash and mime_type to all TranscriptionJob instances")
