"""Print the inactive integration protocol, never evaluate or activate a cohort."""
import argparse
import json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--benchmark-version', choices=('0.5.0', '0.6.0'), required=True)
    args = parser.parse_args()
    print(json.dumps(dict(benchmark_version=args.benchmark_version, preparation_only=True,
                          dispatch_enabled=False, production_default_changed=False,
                          protocol='docs/MLWE_V060_IMPLEMENTATION_PROTOCOL.md',
                          required_before_v060_dispatch=['source-bound supervisor and auditor reviews',
                              'native complete fault suite', 'native 30-pair unchanged thresholds',
                              'contract adoption', 'separate worker and participant artifacts',
                              'fresh audited epoch and reference costs']), sort_keys=True))


if __name__ == '__main__':
    main()
