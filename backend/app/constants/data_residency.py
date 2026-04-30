from typing import Dict, FrozenSet

RESIDENCY_REGION_MAP: Dict[str, FrozenSet[str]] = {
    "EU": frozenset({
        "eu-west-1", "eu-west-2", "eu-west-3",
        "eu-central-1", "eu-central-2",
        "eu-north-1", "eu-south-1", "eu-south-2",
        "eusc-de-east-1",  # AWS European Sovereign Cloud (Germany)
    }),
    "CA": frozenset({"ca-central-1", "ca-west-1"}),
    "US": frozenset({"us-east-1", "us-east-2", "us-west-1", "us-west-2"}),
    "AP": frozenset({
        "ap-northeast-1", "ap-northeast-2", "ap-northeast-3",
        "ap-south-1", "ap-south-2",
        "ap-southeast-1", "ap-southeast-2", "ap-southeast-3",
        "ap-southeast-4", "ap-southeast-5", "ap-southeast-6", "ap-southeast-7",
        "ap-east-2",
    }),
    "SA": frozenset({"sa-east-1"}),
    "ME": frozenset({"me-central-1", "me-south-1"}),
    "AF": frozenset({"af-south-1"}),
    "IL": frozenset({"il-central-1"}),
    "MX": frozenset({"mx-central-1"}),
}