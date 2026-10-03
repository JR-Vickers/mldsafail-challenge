def solve(instance):
    import os
    import time
    if os.fork() == 0:
        os.fork()
    while True:
        time.sleep(.1)
