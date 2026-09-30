import json
import re

def extract_json_objects(text):
    objects = []
    # Find all occurrences of {"name":
    for match in re.finditer(r'\{\s*"name"\s*:', text):
        start = match.start()
        # Find the matching closing bracket by counting braces
        brace_count = 0
        in_string = False
        escape = False
        
        for i in range(start, len(text)):
            c = text[i]
            if not escape:
                if c == '"':
                    in_string = not in_string
                elif not in_string:
                    if c == '{':
                        brace_count += 1
                    elif c == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            # We found a complete JSON object!
                            raw_json = text[start:i+1]
                            try:
                                parsed = json.loads(raw_json)
                                if "name" in parsed and "arguments" in parsed:
                                    objects.append((raw_json, parsed))
                                    # Replace the found json in the original text with spaces so we don't match inside it again
                                    text = text[:start] + ' '*(i+1-start) + text[i+1:]
                            except Exception as e:
                                print("Parse error:", e)
                            break
            if c == '\\' and not escape:
                escape = True
            else:
                escape = False
    return objects

content = r"""
Scout: Sure! Let's do this.

```json
{"name": "create_directory", "arguments": {"path": "C:\\Users\\Scout\\OneDrive\\Desktop\\captcha_generator"}}
```

```json
{"name": "write_file", "arguments": {"path": "C:\\test", "content": "hi"}}
```
"""
objs = extract_json_objects(content)
print(objs)
