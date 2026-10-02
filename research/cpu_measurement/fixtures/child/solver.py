def solve(instance):
    import os
    pid = os.fork()
    if pid == 0:
        sum(i*i for i in range(2000000))
        os._exit(0)
    os.waitpid(pid, 0)
    return None
