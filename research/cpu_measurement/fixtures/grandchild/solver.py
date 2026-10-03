def solve(instance):
    import os
    child = os.fork()
    if child == 0:
        grandchild = os.fork()
        if grandchild == 0:
            sum(i * i for i in range(2000000))
            os._exit(0)
        os.waitpid(grandchild, 0)
        os._exit(0)
    os.waitpid(child, 0)
    return None
