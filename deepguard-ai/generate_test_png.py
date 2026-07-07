import base64, pathlib
b='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/5+BFwAE/wJ/5HDWAAAAAElFTkSuQmCC'
path=pathlib.Path('test.png')
path.write_bytes(base64.b64decode(b))
print('test.png created')
