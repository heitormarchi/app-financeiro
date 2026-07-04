import json
from pathlib import Path

def merge():
    ast_path = Path('.graphify_ast.json')
    if not ast_path.exists():
        print("AST file missing")
        return
        
    ast = json.loads(ast_path.read_text())
    
    semantic_nodes = [
        {"id":"f_main","label":"FastAPI Main Entry","file_type":"code","source_file":"backend/app/main.py"},
        {"id":"f_router","label":"V1 API Router","file_type":"code","source_file":"backend/app/api/v1/router.py"},
        {"id":"f_conn_ep","label":"Connections Endpoint","file_type":"code","source_file":"backend/app/api/v1/endpoints/connections.py"},
        {"id":"f_trans_ep","label":"Transactions Endpoint","file_type":"code","source_file":"backend/app/api/v1/endpoints/transactions.py"},
        {"id":"f_pluggy_svc","label":"Pluggy API Service","file_type":"code","source_file":"backend/app/services/pluggy_service.py"},
        {"id":"f_enrich_svc","label":"Transaction Enrichment","file_type":"code","source_file":"backend/app/services/enrichment_service.py"},
        {"id":"f_insight_svc","label":"Financial Insights","file_type":"code","source_file":"backend/app/services/insight_service.py"},
        {"id":"f_db_models","label":"SQLAlchemy Models","file_type":"code","source_file":"backend/app/models/models.py"},
        {"id":"f_schemas","label":"Pydantic Schemas","file_type":"code","source_file":"backend/app/schemas/schemas.py"},
        {"id":"d_openfinance","label":"OpenFinance Strategy","file_type":"document","source_file":"historico-claude-chat/openfinance.md"},
        {"id":"d_saas_niches","label":"B2C SaaS Market Analysis","file_type":"document","source_file":"historico-claude-chat/nichos de saas b2c.md"}
    ]
    
    semantic_edges = [
        {"source":"f_main","target":"f_router","relation":"references","confidence":"INFERRED","confidence_score":0.95},
        {"source":"f_router","target":"f_conn_ep","relation":"references","confidence":"INFERRED","confidence_score":0.95},
        {"source":"f_router","target":"f_trans_ep","relation":"references","confidence":"INFERRED","confidence_score":0.95},
        {"source":"f_conn_ep","target":"f_pluggy_svc","relation":"calls","confidence":"INFERRED","confidence_score":0.9},
        {"source":"f_trans_ep","target":"f_enrich_svc","relation":"calls","confidence":"INFERRED","confidence_score":0.85},
        {"source":"f_enrich_svc","target":"f_insight_svc","relation":"calls","confidence":"INFERRED","confidence_score":0.75},
        {"source":"f_pluggy_svc","target":"f_db_models","relation":"shares_data_with","confidence":"INFERRED","confidence_score":0.8},
        {"source":"f_trans_ep","target":"f_schemas","relation":"references","confidence":"INFERRED","confidence_score":0.9},
        {"source":"d_openfinance","target":"f_pluggy_svc","relation":"rationale_for","confidence":"INFERRED","confidence_score":0.85},
        {"source":"d_saas_niches","target":"f_main","relation":"conceptually_related_to","confidence":"INFERRED","confidence_score":0.7}
    ]
    
    seen = {n['id'] for n in ast['nodes']}
    merged_nodes = list(ast['nodes'])
    for n in semantic_nodes:
        if n['id'] not in seen:
            merged_nodes.append(n)
            seen.add(n['id'])
            
    merged = {
        'nodes': merged_nodes,
        'edges': ast['edges'] + semantic_edges,
        'hyperedges': [],
        'input_tokens': 0,
        'output_tokens': 0
    }
    
    Path('.graphify_extract.json').write_text(json.dumps(merged, indent=2))
    print(f"Merged {len(merged_nodes)} nodes and {len(merged['edges'])} edges")

if __name__ == "__main__":
    merge()
