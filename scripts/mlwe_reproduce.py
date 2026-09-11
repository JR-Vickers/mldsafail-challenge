"""Compare two clean worker builds with the reviewed frozen image (public fixtures only)."""
import argparse
import json
from pathlib import Path
import subprocess

from mldsafail.benchmark_v050.generator import generate_mlwe
from mldsafail.benchmark_v050.models import canonical_json
from research.primitive_selection.generator import generate_mlwe as frozen_generate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image-a', required=True)
    parser.add_argument('--image-b', required=True)
    parser.add_argument('--frozen-image', default='mldsafail-primitive-study:validation-v2')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    normalized = []
    for profile in ['small', 'medium', 'large']:
        for eta in [1, 2]:
            for seed in [0, 1]:
                public = generate_mlwe(profile, seed, eta).public.to_dict()
                assert canonical_json(public) == canonical_json(frozen_generate(profile, seed, eta).public.to_dict())
                for solver in ['primal-lll', 'hybrid-bdd', 'exhaustive']:
                    request = canonical_json({'instance': public, 'solver': solver})
                    outputs = []
                    for image, module in [(args.image_a,'mldsafail.benchmark_v050.worker'), (args.image_b,'mldsafail.benchmark_v050.worker'), (args.frozen_image,'research.primitive_selection.worker')]:
                        raw = subprocess.check_output(['docker','run','--rm','--network=none','--read-only','--cpus=1','--memory=2g','--entrypoint=python','-i',image,'-m',module], input=request, timeout=65)
                        response = json.loads(raw)
                        assert not response.get('error'), response
                        outputs.append({'candidate':response.get('candidate'), 'verification':response.get('verification'),
                                        'parameters':response.get('solver_parameters'), 'counters':response.get('diagnostic_counters')})
                    assert outputs[0] == outputs[1] == outputs[2], (profile, eta, seed, solver, outputs)
                    normalized.append({'profile':profile,'eta':eta,'seed':seed,'solver':solver,'input':public,'output':outputs[0]})
                    print(profile, eta, seed, solver, 'match', flush=True)
    (args.output / 'normalized.json').write_text(json.dumps(normalized, sort_keys=True, indent=2)+'\n')
    artifacts = [json.loads(subprocess.check_output(['docker','run','--rm','--entrypoint=cat',image,'/artifacts.json'])) for image in [args.image_a,args.image_b]]
    assert artifacts[0] == artifacts[1]
    (args.output / 'artifacts.json').write_text(json.dumps(artifacts[0],sort_keys=True,indent=2)+'\n')
    result = {'fixture_match':True,'normalized_output_match':True,'dependency_artifacts_match':True,'cases':len(normalized),
              'images': {image: json.loads(subprocess.check_output(['docker','image','inspect',image]))[0]['Id'] for image in [args.image_a,args.image_b,args.frozen_image]}}
    (args.output / 'result.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')


if __name__ == '__main__':
    main()
