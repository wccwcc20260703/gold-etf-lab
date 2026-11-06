"""Restore and validate public derived execution cache for independent model audits."""
import hashlib,json,pathlib,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1];D=ROOT/'data/futures';receipt=json.loads((D/'factor-outcomes-receipt.json').read_text());source=D/receipt['file'];assert hashlib.sha256(source.read_bytes()).hexdigest()==receipt['sha256']
target=D/'cache'/(receipt['cacheKey']+'.npz');target.parent.mkdir(exist_ok=True)
if not target.exists():shutil.copyfile(source,target)
assert hashlib.sha256(target.read_bytes()).hexdigest()==receipt['sha256'];print(json.dumps({'executionCache':'verified','bytes':source.stat().st_size,'sha256':receipt['sha256']}))
