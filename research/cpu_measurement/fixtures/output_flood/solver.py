def solve(instance):
    import os
    for _ in range(2048):
        os.write(1, b'x' * 1024)
    return None
