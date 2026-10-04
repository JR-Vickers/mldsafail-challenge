"""Independent bounded create acknowledgement; survives accounting owner loss."""
import argparse
import base64
import json
from pathlib import Path
import re
import subprocess
from deploy.owned_client import capture
from research.cpu_measurement.ownership import publish


def mutate(argv, receipt, epoch, operation):
    buffers={'stdout':bytearray(),'stderr':bytearray()}
    process=None
    result=dict(schema='mldsafail.cpu-mutation-receipt.v1',daemon_epoch=epoch,operation=operation,
                acknowledged=False,container_id=None,returncode=None)
    try:
        from deploy.owned_daemon import load_manifest, verify_environment
        manifest=verify_environment(load_manifest())
        if manifest['epoch']!=epoch: raise RuntimeError('Daemon epoch changed before mutation')
        process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        capture(process,None,30,buffers,lambda:None,cap=1024*1024)
        output=bytes(buffers['stdout']).strip()
        result['returncode']=process.returncode
        if process.returncode==0 and re.fullmatch(b'[0-9a-f]{64}',output):
            result.update(acknowledged=True,container_id=output.decode())
    except BaseException as error:
        result['error_type']=type(error).__name__
    finally:
        errors=[]
        if process is not None:
            try:
                if process.poll() is None: process.kill()
                process.wait(timeout=15)
            except BaseException as error: errors.append(type(error).__name__)
            for stream in (process.stdout,process.stderr):
                try: stream.close()
                except BaseException as error: errors.append(type(error).__name__)
        result['cleanup_errors']=errors
        if errors: result['acknowledged']=False
        result['raw_stdout_base64']=base64.b64encode(buffers['stdout']).decode()
        result['raw_stderr_base64']=base64.b64encode(buffers['stderr']).decode()
        publish(Path(receipt),result)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--epoch',required=True)
    parser.add_argument('--operation',choices=['create','start'],required=True)
    parser.add_argument('command',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    if not args.command or args.command[:2] != ['docker',args.operation]:
        raise ValueError('Only trusted Docker mutation is supported')
    mutate(args.command,args.receipt,args.epoch,args.operation)


if __name__=='__main__': main()
