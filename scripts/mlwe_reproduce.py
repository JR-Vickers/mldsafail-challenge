"""Compare two clean worker builds with the reviewed frozen image (public fixtures only)."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.reproduction_lifecycle import ReproductionRun

from mldsafail.benchmark_v050.generator import generate_mlwe
from mldsafail.benchmark_v050.models import canonical_json
from research.primitive_selection.generator import generate_mlwe as frozen_generate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image-a')
    parser.add_argument('--image-b')
    parser.add_argument('--frozen-image')
    parser.add_argument('--cleanup', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    images = [] if args.cleanup else [args.image_a, args.image_b, args.frozen_image]
    with ReproductionRun(args.output, images, cleanup_only=args.cleanup) as owned:
        if args.cleanup:
            return
        reproduce(args, owned)


def reproduce(args, owned):
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
                        raw = owned.invoke(image, ['-m', module], request)
                        response = json.loads(raw)
                        assert not response.get('error'), response
                        outputs.append({'candidate':response.get('candidate'), 'verification':response.get('verification'),
                                        'parameters':response.get('solver_parameters'), 'counters':response.get('diagnostic_counters')})
                    assert outputs[0] == outputs[1] == outputs[2], (profile, eta, seed, solver, outputs)
                    normalized.append({'profile':profile,'eta':eta,'seed':seed,'solver':solver,'input':public,'output':outputs[0]})
                    print(profile, eta, seed, solver, 'match', flush=True)
    (args.output / 'normalized.json').write_text(json.dumps(normalized, sort_keys=True, indent=2)+'\n')
    artifacts = [json.loads(owned.invoke(image, ['/artifacts.json'])) for image in [args.image_a,args.image_b]]
    assert artifacts[0] == artifacts[1]
    (args.output / 'artifacts.json').write_text(json.dumps(artifacts[0],sort_keys=True,indent=2)+'\n')
    result = {'fixture_match':True,'normalized_output_match':True,'dependency_artifacts_match':True,'cases':len(normalized),
              'images': {image: json.loads(owned.command(['docker','image','inspect',image], timeout=10).stdout)[0]['Id'] for image in [args.image_a,args.image_b,args.frozen_image]}}
    (args.output / 'result.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')


if __name__ == '__main__':
    main()
