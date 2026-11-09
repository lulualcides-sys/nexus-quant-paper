"""Extract public reference evidence (not source indicator) from Greenhouse offer HTML.

No member login, no checkout, no protected scripts, no JS execution.
Reports short code contexts for analyst, not a proprietary rule or raw code dump.
"""
import hashlib, html, json, re, urllib.request
from urllib.parse import urlparse

PAGE="https://lojadagreenhouse.com.br/ofertatracker/"
PATTERNS={
    "pub_record_time":r"\b09:0[0-9]\b",
    "public_day03":r"03[/.-]11[/.-]2026",
    "public_day04":r"04[/.-]11[/.-]2026",
    "public_next_control_markup":r"Pr[oó]ximo\s*</button>",
    "signal_data_var":r"(?:signals|sinais|trades|signalData|trackerSignals)[\s=:]{1,12}[\[{]",
    "video_id":r"(?:ytimg\.com/vi/|youtube\.com/embed/|youtu\.be/)([A-Za-z0-9_-]{11})",
    "data_video_attrs":r"\bdata-(?:youtube|video|yt|clip)[A-Za-z0-9-]*\s*=\s*[\"'][^\"']{2,180}",
    "chart_label":r"Sinal\s*01",
    "play_control":r"(?:play|pr[óo]ximo|avançar|assistir)",
}
def main():
    req=urllib.request.Request(PAGE,headers={"User-Agent":"Mozilla/5.0 public indicator research"})
    with urllib.request.urlopen(req,timeout=25) as r:
        raw=r.read(2_000_000)
    data=html.unescape(raw.decode("utf-8-sig",errors="replace").replace("\\/","/"))
    report={"url":PAGE,"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),
            "youtube_ids":[],"patterns":{}}
    for name,pattern in PATTERNS.items():
        all_hits=list(re.finditer(pattern,data,re.I))
        # Names/locations, never interpret arbitrary JS as trading algorithm.
        contexts=[]
        for m in all_hits[:10]:
            a=max(0,m.start()-140);b=min(len(data),m.end()+240)
            snippet=" ".join(re.sub(r"<[^>]+>"," ",data[a:b]).split())
            contexts.append({"offset":m.start(),"snippet":snippet[:360]})
            if name=="video_id":
                report["youtube_ids"].append(m.group(1))
        report["patterns"][name]={"matches":len(all_hits),"examples":contexts}
    report["youtube_ids"]=sorted(set(report["youtube_ids"]))
    # Inspect ONLY short excerpts of the public chart-replay JavaScript,
    # looking for declared recorded labels, not the proprietary indicator.
    for needle in ("var DAYS=['03/11','04/11']", "ghv-registro", "09:03", "var DAYS="):
        p=data.find(needle)
        if p>=0:
            report.setdefault("public_replay_js_excerpts",[]).append(
                {"needle":needle,"offset":p,"excerpt":data[max(0,p-1800):p+3800][:5600]})
    # Public YouTube thumbnails are not proof the videos were watched.
    report["youtube_embed_context"]=[]
    for ident in report["youtube_ids"]:
        matches=[x for x in re.finditer(re.escape(ident),data)]
        if matches:
            m=matches[0]
            ctx=" ".join(re.sub(r"<[^>]+>"," ",data[max(0,m.start()-500):m.end()+450]).split())
            report["youtube_embed_context"].append({"id":ident,"context":ctx[:650]})

    print("PUBLIC_SIGNAL_SOURCE_START")
    print(json.dumps(report,ensure_ascii=False,indent=2)[:23000])
    print("PUBLIC_SIGNAL_SOURCE_END")
    from pathlib import Path
    out=Path("research/results");out.mkdir(parents=True,exist_ok=True)
    (out/"greenhouse_public_signal_source_catalog.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__":main()
