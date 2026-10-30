"""Stand-in for fm-1-research-lab's review gate: accept only stock V15."""
import hashlib, sys
STOCK_V15 = "db1642b2b6fa5c2cccb11ffd13878068bb28601678d3644049f99dc40e7edb8a"
def require_reviewed(path):
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if h != STOCK_V15:
        sys.exit(f"refusing {path}: sha256 {h} is not stock FM-1_015 (V15)")
