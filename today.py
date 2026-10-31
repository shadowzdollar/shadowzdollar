import os, re, requests
from datetime import datetime, timezone

USER = os.environ["USER_NAME"]
TOKEN = os.environ["ACCESS_TOKEN"]
HEAD = {"Authorization": f"bearer {TOKEN}"}
FILE = "dark_mode_v2.svg"


def gql(query, variables=None):
    r = requests.post("https://api.github.com/graphql",
                      json={"query": query, "variables": variables or {}},
                      headers=HEAD, timeout=60)
    r.raise_for_status()
    d = r.json()
    if "errors" in d:
        raise Exception(d["errors"])
    return d["data"]


def basics():
    q = """query($login:String!){user(login:$login){id createdAt
      followers{totalCount} repositories(ownerAffiliations:OWNER){totalCount}}}"""
    return gql(q, {"login": USER})["user"]


def commits(created_at):
    q = """query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){
      contributionsCollection(from:$from,to:$to){
        totalCommitContributions restrictedContributionsCount}}}"""
    total = 0
    for y in range(int(created_at[:4]), datetime.now(timezone.utc).year + 1):
        d = gql(q, {"login": USER, "from": f"{y}-01-01T00:00:00Z",
                    "to": f"{y}-12-31T23:59:59Z"})
        c = d["user"]["contributionsCollection"]
        total += c["totalCommitContributions"] + c["restrictedContributionsCount"]
    return total


def repo_list():
    q = """query($login:String!,$cursor:String){user(login:$login){
      repositories(first:50,after:$cursor,ownerAffiliations:OWNER){
        pageInfo{hasNextPage endCursor} nodes{name owner{login}}}}}"""
    repos, cursor = [], None
    while True:
        d = gql(q, {"login": USER, "cursor": cursor})["user"]["repositories"]
        repos += d["nodes"]
        if not d["pageInfo"]["hasNextPage"]:
            return repos
        cursor = d["pageInfo"]["endCursor"]


def loc(user_id):
    q = """query($owner:String!,$name:String!,$uid:ID!,$cursor:String){
      repository(owner:$owner,name:$name){defaultBranchRef{target{... on Commit{
        history(first:100,after:$cursor,author:{id:$uid}){
          pageInfo{hasNextPage endCursor} nodes{additions deletions}}}}}}}"""
    add = dele = 0
    for repo in repo_list():
        cursor = None
        while True:
            d = gql(q, {"owner": repo["owner"]["login"], "name": repo["name"],
                        "uid": user_id, "cursor": cursor})["repository"]
            ref = d["defaultBranchRef"]
            if not ref:
                break
            h = ref["target"]["history"]
            for n in h["nodes"]:
                add += n["additions"]
                dele += n["deletions"]
            if not h["pageInfo"]["hasNextPage"]:
                break
            cursor = h["pageInfo"]["endCursor"]
    return add, dele


def put(svg, tag, value):
    return re.sub(rf'(id="{tag}">)[^<]*(<)', rf'\g<1>{value}\g<2>', svg)


u = basics()
a, d = loc(u["id"])
stats = {
    "repo_data": f'{u["repositories"]["totalCount"]:,}',
    "commit_data": f'{commits(u["createdAt"]):,}',
    "follower_data": f'{u["followers"]["totalCount"]:,}',
    "loc_data": f"{a - d:,} ( {a:,}++, {d:,}-- )",
}

svg = open(FILE, encoding="utf-8").read()
for k, v in stats.items():
    svg = put(svg, k, v)
open(FILE, "w", encoding="utf-8").write(svg)
print(stats)
