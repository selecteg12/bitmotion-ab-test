from pathlib import Path
from urllib.request import urlretrieve

data=Path(__file__).resolve().parent/'data'
data.mkdir(exist_ok=True)
for name in ['ab_test_participants.csv','ab_test_events.zip']:
    target=data/name
    if not target.exists():
        urlretrieve('https://code.s3.yandex.net/datasets/'+name,target)
    print(target.name,target.stat().st_size)
