import sys, json, urllib.request

job_id = sys.argv[1] if len(sys.argv) > 1 else "174b7253-371b-4ba9-81e8-bc5a48dc0f3b"
url = f"http://localhost:8000/api/simulations/{job_id}"
data = json.loads(urllib.request.urlopen(url).read())
result = data.get("result", {})
agents = result.get("summary", {}).get("agents", [])

print(f"エージェント数: {len(agents)}")
print()
for a in agents:
    mode = a.get("mode", "individual")
    rc = a.get("represents_count", 1)
    tag = f" (x{rc})" if rc > 1 else ""
    name = a["name"]
    atype = a.get("type", "")
    desc = a.get("description", "")[:60]
    print(f"  [{mode:10s}] {name}{tag} -- {atype} -- {desc}")

print()
rounds = result.get("rounds", [])
print(f"ラウンド数: {len(rounds)}")
if rounds:
    first_d = rounds[0]["market_state"]["dimensions"]
    last_d = rounds[-1]["market_state"]["dimensions"]
    print(f"R1:  ua={first_d.get('user_adoption',0):.3f} cp={first_d.get('competitive_pressure',0):.3f} ma={first_d.get('market_awareness',0):.3f}")
    print(f"R{len(rounds)}: ua={last_d.get('user_adoption',0):.3f} cp={last_d.get('competitive_pressure',0):.3f} ma={last_d.get('market_awareness',0):.3f}")
