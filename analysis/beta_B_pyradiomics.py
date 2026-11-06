import os, glob, csv, gc, numpy as np, SimpleITK as sitk, logging
from scipy import ndimage as ndi
from radiomics import featureextractor
logging.getLogger('radiomics').setLevel(logging.ERROR)
ROOT=os.environ.get("KITS23_ROOT", os.path.expanduser("~/KiTS23")); RAW=ROOT+"/kits23/dataset"; CYST=3; CONN=np.ones((3,3,3),int); MARGIN=16
FOLD_PRED={0:"holdout_pipeline/soft_majority_rule3_typex"}
for k in (1,2,3,4): FOLD_PRED[k]=f"repro_check/scratch_fold{k}/final_rule3_typex"
ext=featureextractor.RadiomicsFeatureExtractor(binWidth=25)
ext.enableImageTypeByName('Wavelet')   # Original(預設)+ Wavelet ≈ 文獻 386
rows=[]; nskip=0
for fold,pd in FOLD_PRED.items():
    for p in sorted(glob.glob(os.path.join(ROOT,pd)+"/KiTS23_*.nii.gz")):
        cid=os.path.basename(p).replace("KiTS23_","").replace(".nii.gz","")
        pr=sitk.GetArrayFromImage(sitk.ReadImage(p))
        if not (pr==CYST).any(): continue
        try:
            img_sitk=sitk.ReadImage(os.path.join(RAW,f"case_{cid}","imaging.nii.gz"))
            gt=sitk.GetArrayFromImage(sitk.ReadImage(os.path.join(RAW,f"case_{cid}","segmentation.nii.gz")))
        except: continue
        img=sitk.GetArrayFromImage(img_sitk); sp=img_sitk.GetSpacing()   # sp=(x,y,z)
        if pr.shape!=gt.shape or img.shape!=pr.shape: del img,pr,gt; gc.collect(); continue
        gt_has=bool((gt==CYST).any()); gt_cyst=(gt==CYST); lab,n=ndi.label(pr==CYST,CONN)
        for i in range(1,n+1):
            m=lab==i; sz=int(m.sum()); ov=int((m&gt_cyst).sum())
            grp="C_fp_neg" if not gt_has else ("B_tp" if ov>0 else "skip")
            if grp=="skip" or sz<8:
                if grp!="skip": nskip+=1
                continue
            zz,yy,xx=np.where(m)
            z0,z1=max(0,zz.min()-MARGIN),min(m.shape[0],zz.max()+MARGIN+1)
            y0,y1=max(0,yy.min()-MARGIN),min(m.shape[1],yy.max()+MARGIN+1)
            x0,x1=max(0,xx.min()-MARGIN),min(m.shape[2],xx.max()+MARGIN+1)
            ic=np.ascontiguousarray(img[z0:z1,y0:y1,x0:x1])
            mc=np.ascontiguousarray(m[z0:z1,y0:y1,x0:x1].astype(np.uint8))
            im=sitk.GetImageFromArray(ic); im.SetSpacing(sp)
            ms=sitk.GetImageFromArray(mc); ms.CopyInformation(im)
            try:
                res=ext.execute(im,ms,label=1)
                f={k:float(v) for k,v in res.items() if not k.startswith('diagnostics')}
                f.update(fold=fold,case=cid,group=grp,cc=i,vox=sz); rows.append(f)
            except Exception: nskip+=1
        del pr,gt,img,gt_cyst,lab; gc.collect()
    print(f"fold{fold} done, rows={len(rows)}",flush=True)
keys=sorted(set().union(*[set(r.keys()) for r in rows]))
with open(ROOT+"/beta_pyradiomics_features.csv","w",newline="") as fo:
    w=csv.DictWriter(fo,fieldnames=keys); w.writeheader(); w.writerows(rows)
from collections import Counter
nf=len([k for k in keys if k not in('fold','case','group','cc','vox')])
print("DONE",len(rows),"comps",dict(Counter(r['group'] for r in rows)),f"| {nf} features | skip {nskip}")
