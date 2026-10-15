"""
REAL surprise-weighted memory for REA analyses
"""
from datetime import datetime

class TitansMemoryREA:
    def __init__(self):
        self.store = {}
        self.graph = {}
    
    def calculate_surprise(self, analysis):
        sha = analysis.get('sha256','')
        is_new = sha not in self.store
        entropy = analysis.get('recon',{}).get('entropy',{}).get('overall',0)
        if isinstance(entropy, dict):
            entropy = entropy.get('overall',0)
        strings_count = len(analysis.get('strings',[]))
        confidence = analysis.get('confidence',{}).get('overall',0)
        if isinstance(confidence, dict):
            confidence = confidence.get('overall',0)
        surprise = 0.0
        if is_new: surprise += 0.5
        if entropy > 7.2: surprise += 0.3
        if strings_count > 50: surprise += 0.2
        surprise *= max(0.1, confidence)
        return min(1.0, round(surprise,3))
    
    async def store(self, event):
        payload = event.get('payload', event)
        sha = payload.get('sha256','') or payload.get('id','')
        surprise = self.calculate_surprise(payload)
        record = {
            'id': payload.get('id',''),
            'sha256': sha,
            'surprise_score': surprise,
            'timestamp': datetime.utcnow().isoformat()
        }
        self.store[sha] = record
        return record
    
    def query(self, file_type=None, min_surprise=0.0):
        results = list(self.store.values())
        results = [r for r in results if r['surprise_score'] >= min_surprise]
        return sorted(results, key=lambda x: x['surprise_score'], reverse=True)

memory = TitansMemoryREA()
