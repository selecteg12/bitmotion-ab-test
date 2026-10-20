import json
from pathlib import Path
import numpy as np
import pandas as pd
from math import erfc, sqrt
from statistics import NormalDist
def normal_sf(z): return .5*erfc(float(z)/sqrt(2))
def srm_p(counts):
    observed=np.asarray(counts,dtype=float)
    expected=observed.sum()/2
    chi2=float(np.sum((observed-expected)**2/expected))
    return erfc(sqrt(chi2/2))
import argparse
ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description='Reproduce the BitMotion A/B analysis')
parser.add_argument('--data-dir',type=Path,default=ROOT/'data')
parser.add_argument('--output',type=Path,default=ROOT/'results.json')
args=parser.parse_args()
DATA=args.data_dir
p=pd.read_csv(DATA/'ab_test_participants.csv',dtype={'user_id':'string'})
e=pd.read_csv(DATA/'ab_test_events.zip',parse_dates=['event_dt'],low_memory=False,dtype={'user_id':'string'})
cohort=p.loc[p.ab_test.eq('interface_eu_test')].copy()
cross=p.groupby('user_id').ab_test.nunique()
cross=set(cross[cross.gt(1)].index)
clean=cohort.loc[~cohort.user_id.isin(cross)].copy()
assert clean.user_id.is_unique
reg=e.loc[e.event_name.eq('registration')].groupby('user_id').event_dt.min().rename('registered_at')
clean=clean.merge(reg,on='user_id',how='left',validate='one_to_one')
end=e.event_dt.max()
clean['mature']=clean.registered_at.notna() & ((clean.registered_at+pd.Timedelta(days=7))<=end)
events=e.merge(clean[['user_id','group','registered_at','mature']],on='user_id',how='inner',validate='many_to_one')
events['age']=events.event_dt-events.registered_at

def metrics(users,ev):
    buyers=set(ev.loc[ev.event_name.eq('purchase'),'user_id'])
    u=users.assign(buyer=users.user_id.isin(buyers))
    g=u.groupby('group').buyer.agg(['size','sum','mean'])
    na,nb=int(g.loc['A','size']),int(g.loc['B','size'])
    xa,xb=int(g.loc['A','sum']),int(g.loc['B','sum'])
    pa,pb=xa/na,xb/nb
    pooled=(xa+xb)/(na+nb)
    z=(pb-pa)/np.sqrt(pooled*(1-pooled)*(1/na+1/nb))
    se=np.sqrt(pa*(1-pa)/na+pb*(1-pb)/nb)
    return {'A':{'n':na,'buyers':xa,'cr':pa},'B':{'n':nb,'buyers':xb,'cr':pb},'difference_pp':100*(pb-pa),'relative_uplift_pct':100*(pb/pa-1),'p_one_sided':normal_sf(z),'p_two_sided':2*normal_sf(abs(z)),'difference_ci95_pp':[100*((pb-pa)-NormalDist().inv_cdf(.975)*se),100*((pb-pa)+NormalDist().inv_cdf(.975)*se)]}

legacy=events[events.age.dt.days.le(7)]
strict=events[events.age.ge(pd.Timedelta(0)) & events.age.lt(pd.Timedelta(days=7))]
mature_users=clean[clean.mature]
mature_events=strict[strict.mature]
result={'raw_test_users':len(cohort),'excluded_cross_test_users':int(cohort.user_id.isin(cross).sum()),'clean_users':len(clean),'missing_registration':int(clean.registered_at.isna().sum()),'incomplete_7day_window':int((~clean.mature & clean.registered_at.notna()).sum()),'capture_end':str(end),'legacy_up_to_7_calendar_day_inclusive':metrics(clean,legacy),'strict_first_168hours':metrics(clean,strict),'strict_mature_users':metrics(mature_users,mature_events),'srm_clean_p':srm_p(clean.group.value_counts()),'srm_mature_p':srm_p(mature_users.group.value_counts())}
devices=pd.crosstab(mature_users.group,mature_users.device)
result['device_counts']=devices.to_dict()
result['versions']={'pandas':pd.__version__,'numpy':np.__version__}
args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
