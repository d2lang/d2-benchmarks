"""Deterministic synthetic records test reporting logic; these are not benchmarks."""
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

from benchmarks.report import generate


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def mock_run(self, values=None, status="completed", formats=("svg",), smoke=False, fixtures=None):
        values=values or {("a","d2-dagre"):[1,2,3,4,5],("a","graphviz-dot"):[2,4,6,8,10],
                          ("b","d2-dagre"):[10,20,30,40,50],("b","graphviz-dot"):[5,10,15,20,25]}
        fixtures=fixtures or [{"id":f,"title":"Fixture "+f,"counts":{"leaf_nodes":2,"groups":0,"edges":1},
                   "png_density":.5 if f=="b" else 2.0,"primary_png":f!="b"} for f in ("a","b")]
        jobs,records=[],[]
        for fixture in fixtures:
            for tool in ("d2-dagre","graphviz-dot"):
                for fmt in formats:
                    f=fixture["id"];output=f"renders/{tool}/{f}.{fmt}";path=self.root/output;path.parent.mkdir(parents=True,exist_ok=True)
                    content=b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="60"><text x="5" y="20">Synthetic test</text></svg>'
                    path.write_bytes(content)
                    job={"id":f"{f}/{tool}/{fmt}","fixture":f,"tool":tool,"format":fmt,
                         "raster_density":fixture["png_density"] if fmt=="png" else None,"primary":fixture["primary_png"] if fmt=="png" else True,
                         "input":f"inputs/{f}.txt","input_sha256":"mock-input-hash","command":["mock-renderer"],"output":output}
                    jobs.append(job)
                    for i,wall in [(-1,10000)]+list(enumerate([v for v in values[f,tool] for _ in range(2)])):
                        records.append({**job,"round":i,"warmup":i<0,"utc":"2000-01-01T00:00:00Z","loadavg":[0,0,0],"wall_ms":wall,
                                        "returncode":0,"success":True,"stdout":"","stderr":"",
                                        "image":{"bytes":len(content),"sha256":hashlib.sha256(content).hexdigest(),"width":100,"height":60,"pixels":6000 if fmt=="png" else None}})
        meta={"schema_version":1,"run_id":"synthetic-test","started_utc":"2000-01-01T00:00:00Z","completed_utc":"2000-01-01T00:01:00Z",
              "status":status,"seed":123,"warmups":1,"repetitions":10,"tools":["d2-dagre","graphviz-dot"],"fixtures":fixtures,
              "jobs":jobs,"environment":{"description":"Synthetic test environment"},"smoke":smoke}
        self.save(meta,records)
        return meta,records

    def save(self,meta,records):
        (self.root/"run.json").write_text(json.dumps(meta))
        (self.root/"raw.jsonl").write_text("".join(json.dumps(r)+"\n" for r in records))

    def test_known_medians_and_matched_ratios(self):
        self.mock_run()
        s=generate(self.root,bootstrap=200)
        self.assertEqual(s["cases"][0]["timing_ms"]["median"],3)
        self.assertEqual(s["cases"][0]["timing_ms"]["samples"],[1,1,2,2,3,3,4,4,5,5])
        self.assertEqual(s["cases"][0]["timing_ms"]["max"],5)  # excluded warm-up is 10000
        self.assertTrue(s["groups"][0]["ranking_available"])
        ag={a["tool"]:a for a in s["groups"][0]["aggregates"]}
        self.assertAlmostEqual(ag["d2-dagre"]["geomean_median_ms"],math.sqrt(3*30))
        self.assertAlmostEqual(ag["graphviz-dot"]["baseline_over_tool_ratio"],1)
        self.assertEqual(ag["d2-dagre"]["ratio_ci95"],[1,1])
        self.assertEqual(ag["graphviz-dot"]["ratio_ci95"],[1,1])  # joint round resampling preserves known fixed ratios
        for a in ag.values():
            lo,hi=a["geomean_median_ci95_ms"]
            self.assertLessEqual(lo,a["geomean_median_ms"])
            self.assertGreaterEqual(hi,a["geomean_median_ms"])
        self.assertEqual(s["completeness"]["successes"],40)
        for name in ("report.md","summary.json","summary.csv","index.html"):
            self.assertTrue((self.root/name).is_file())
        self.assertIn("synthetic-test",(self.root/"index.html").read_text())

    def test_failed_attempt_does_not_make_success_only_leaderboard(self):
        meta,rows=self.mock_run()
        row=next(r for r in rows if r["fixture"]=="a" and r["tool"]=="graphviz-dot" and r["round"]==2)
        row.update(success=False,returncode=2,stderr="synthetic failure")
        self.save(meta,rows);s=generate(self.root,bootstrap=100)
        c=next(c for c in s["cases"] if c["fixture"]=="a" and c["tool"]=="graphviz-dot")
        self.assertEqual((c["successes"],c["failures"],c["expected_measured"]),(9,1,10))
        self.assertFalse(s["groups"][0]["ranking_available"])
        self.assertIsNone(s["groups"][0]["ranking"])
        self.assertEqual(s["groups"][0]["aggregates"],[])
        self.assertIn("synthetic failure",(self.root/"index.html").read_text())

    def test_missing_attempt_and_missing_plan_are_explicit(self):
        meta,rows=self.mock_run()
        rows=[r for r in rows if not (r["fixture"]=="a" and r["tool"]=="graphviz-dot" and r["round"]==1)]
        missing=next(j for j in meta["jobs"] if j["fixture"]=="b" and j["tool"]=="graphviz-dot")
        meta["jobs"].remove(missing);rows=[r for r in rows if r["id"]!=missing["id"]]
        self.save(meta,rows);s=generate(self.root,bootstrap=50)
        self.assertEqual(len(s["cases"]),4)
        self.assertEqual(s["completeness"]["missing_measurements"],11)
        self.assertTrue(next(c for c in s["cases"] if c["fixture"]=="b" and c["tool"]=="graphviz-dot")["missing_plan"])
        self.assertFalse(s["groups"][0]["ranking_available"])

    def test_duplicate_round_invalidates_completeness(self):
        meta,rows=self.mock_run();rows.append(dict(next(r for r in rows if r["round"]==0)))
        self.save(meta,rows);s=generate(self.root,bootstrap=20)
        self.assertEqual(s["cases"][0]["duplicate_rounds"],[0])
        self.assertFalse(s["groups"][0]["ranking_available"])

    def test_bootstrap_is_deterministic_and_bounds_median(self):
        self.mock_run()
        a=generate(self.root,bootstrap=300)
        files={name:(self.root/name).read_bytes() for name in ("summary.json","summary.csv","report.md","index.html")}
        b=generate(self.root,bootstrap=300)
        self.assertEqual(a,b)
        self.assertEqual(a["bootstrap"]["seed_text"],str(a["bootstrap"]["seed"]))
        for name,contents in files.items():self.assertEqual((self.root/name).read_bytes(),contents)
        for c in a["cases"]:
            lo,hi=c["timing_ms"]["median_ci95"];self.assertLessEqual(lo,c["timing_ms"]["median"]);self.assertGreaterEqual(hi,c["timing_ms"]["median"])

    def test_supplemental_png_is_separate(self):
        self.mock_run(formats=("svg","png"))
        s=generate(self.root,bootstrap=40)
        g={g["id"]:g for g in s["groups"]}
        self.assertEqual(g["svg"]["fixtures"],["a","b"])
        self.assertEqual(g["png-primary"]["fixtures"],["a"])
        self.assertEqual(g["png-supplemental"]["fixtures"],["b"])
        self.assertEqual(g["png-primary"]["density"],2)
        self.assertEqual(g["png-supplemental"]["density"],.5)

    def test_graph_sizes_workload_families_and_formats_are_independent(self):
        fixtures=[{"id":f"basic-{n}","category":"basic","counts":{"leaf_nodes":n},
                   "png_density":2.,"primary_png":True} for n in (2,10,100)]
        fixtures += [{"id":f,"category":"real-world","counts":{"leaf_nodes":n},
                      "png_density":2.,"primary_png":True} for f,n in (("complex-a",10),("complex-b",100))]
        values={(f["id"],t):[f["counts"]["leaf_nodes"]]*5 for f in fixtures for t in ("d2-dagre","graphviz-dot")}
        meta,rows=self.mock_run(values=values,fixtures=fixtures,formats=("svg","png"))
        summary=generate(self.root,bootstrap=40)
        groups={g["id"]:g for g in summary["groups"]}
        self.assertEqual(list(groups),["basic-2-svg","basic-2-png-primary","basic-10-svg","basic-10-png-primary",
                                       "basic-100-svg","basic-100-png-primary","svg","png-primary"])
        for n in (2,10,100):
            for suffix in ("svg","png-primary"):
                group=groups[f"basic-{n}-{suffix}"]
                self.assertEqual(group["fixtures"],[f"basic-{n}"])
                self.assertEqual((group["category"],group["node_count"]),("basic",n))
                for aggregate in group["aggregates"]:
                    self.assertAlmostEqual(aggregate["geomean_median_ms"],n)
                    for bound in aggregate["geomean_median_ci95_ms"]:self.assertAlmostEqual(bound,n)
        for suffix in ("svg","png-primary"):
            self.assertEqual(groups[suffix]["fixtures"],["complex-a","complex-b"])
            self.assertIsNone(groups[suffix]["node_count"])
            self.assertAlmostEqual(groups[suffix]["aggregates"][0]["geomean_median_ms"],math.sqrt(10*100))
        # A failure suppresses the complete matched comparison for its own group,
        # while independently measured workloads and the other output stay usable.
        next(r for r in rows if r["fixture"]=="basic-10" and r["format"]=="png" and r["round"]==1).update(success=False,returncode=2)
        meta["status"]="failed"  # The real runner finalizes any session with a failed job this way.
        self.save(meta,rows)
        failed=generate(self.root,bootstrap=20)
        self.assertEqual([g["id"] for g in failed["groups"] if not g["ranking_available"]],["basic-10-png-primary"])
        markdown=(self.root/"report.md").read_text()
        self.assertLess(markdown.index("## Performance matrix"),markdown.index("## Method and uncertainty"))
        self.assertIn("| Basic · 10 nodes | PNG 2× | unavailable | unavailable |",markdown)
        self.assertIn("Real-world complex",markdown)

    def test_fatal_and_integrity_errors_suppress_every_workload(self):
        for field in ("fatal_error","input_integrity_errors","tool_integrity_errors","config_integrity_errors"):
            meta,rows=self.mock_run(status="failed",formats=("svg","png"))
            meta[field]="recorded run-wide failure"
            self.save(meta,rows)
            summary=generate(self.root,bootstrap=20)
            self.assertTrue(all(not g["ranking_available"] for g in summary["groups"]))
            self.assertTrue(all(any(field in reason for reason in g["ranking_suppression_reasons"]) for g in summary["groups"]))

    def test_performance_reports_omit_file_sizes_and_verify_assets_by_hash(self):
        meta,rows=self.mock_run(formats=("svg","png"))
        for row in rows:row["image"].pop("bytes")
        self.save(meta,rows)
        summary=generate(self.root,bootstrap=20)
        self.assertTrue(all(case["asset"]["verified"] for case in summary["cases"]))
        self.assertTrue(all(group["ranking_available"] for group in summary["groups"]))
        self.assertTrue(all("pixels" not in a for g in summary["groups"] for a in g["aggregates"]))
        for filename in ("summary.json","summary.csv","report.md","index.html"):
            contents=(self.root/filename).read_text().lower()
            self.assertNotIn("bytes",contents)
            self.assertNotIn("gzip",contents)
        # Dimensions survive solely as retained-image metadata for the gallery.
        self.assertEqual(summary["cases"][0]["asset"]["width"],100)

    def test_incomplete_smoke_and_short_status_suppress_ranking(self):
        for mode in ("incomplete","smoke","short"):
            meta,rows=self.mock_run(status="running" if mode=="incomplete" else "completed",smoke=mode=="smoke")
            if mode=="short":meta["repetitions"]=1;rows=[r for r in rows if r["round"]<=0]
            self.save(meta,rows);s=generate(self.root,bootstrap=10)
            self.assertFalse(s["groups"][0]["ranking_available"])
            self.assertTrue(s["groups"][0]["ranking_suppression_reasons"])

    def test_all_samples_retained_including_extreme_outlier(self):
        values={(f,t):[1,2,3,4,999999] for f in ("a","b") for t in ("d2-dagre","graphviz-dot")}
        self.mock_run(values);s=generate(self.root,bootstrap=30)
        self.assertEqual(s["cases"][0]["timing_ms"]["max"],999999)
        self.assertEqual(s["cases"][0]["timing_ms"]["count"],10)
        self.assertEqual(s["cases"][0]["timing_ms"]["median"],3)

    def test_output_hash_mismatch_disables_ranking(self):
        self.mock_run();(self.root/"renders/d2-dagre/a.svg").write_text("changed")
        s=generate(self.root,bootstrap=10)
        self.assertFalse(s["cases"][0]["asset"]["verified"])
        self.assertFalse(s["groups"][0]["ranking_available"])

    def test_changing_output_hashes_are_visible_without_hiding_valid_timings(self):
        meta,rows=self.mock_run()
        next(r for r in rows if r["round"]==0)["image"]["sha256"]="different-prior-output"
        self.save(meta,rows);s=generate(self.root,bootstrap=30)
        self.assertEqual(s["cases"][0]["measured_output_hash_count"],2)
        self.assertFalse(s["cases"][0]["output_stable"])
        self.assertEqual(s["completeness"]["jobs_with_changing_output_hashes"],1)
        self.assertTrue(s["groups"][0]["ranking_available"])
        self.assertIn("(changed)",(self.root/"report.md").read_text())

    def test_source_and_harness_hashes_are_retained(self):
        meta,rows=self.mock_run()
        meta["harness_sha256"]={"benchmarks/runner.py":"synthetic-harness-hash"}
        meta["corpus_validation"]={"valid":True,"errors":[]}
        manifest=self.root/"inputs/manifest.json";manifest.parent.mkdir(exist_ok=True);manifest.write_text('{"synthetic":true}')
        self.save(meta,rows);s=generate(self.root,bootstrap=10)
        self.assertEqual(s["harness_sha256"],meta["harness_sha256"])
        self.assertEqual(s["corpus_validation"],meta["corpus_validation"])
        self.assertEqual(s["source_hashes"]["inputs/manifest.json"],hashlib.sha256(manifest.read_bytes()).hexdigest())

    def test_partial_raw_line_is_reported_without_dropping_other_jobs(self):
        self.mock_run()
        with (self.root/"raw.jsonl").open("a") as f:f.write('{"interrupted":')
        s=generate(self.root,bootstrap=10)
        self.assertEqual(len(s["cases"]),4);self.assertTrue(s["issues"])
        self.assertFalse(s["groups"][0]["ranking_available"])

    def test_bootstrap_disabled_and_invalid_argument(self):
        self.mock_run();s=generate(self.root,bootstrap=0)
        self.assertIsNone(s["cases"][0]["timing_ms"]["median_ci95"])
        self.assertIsNone(s["groups"][0]["aggregates"][0]["geomean_median_ci95_ms"])
        with self.assertRaises(ValueError):generate(self.root,bootstrap=-1)


if __name__=="__main__":unittest.main()
