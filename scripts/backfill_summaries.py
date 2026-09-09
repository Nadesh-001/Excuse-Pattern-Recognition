import json
from services.ai_service import analyze_excuse_with_ai
from repository.db import execute_query

def backfill_summaries():
    print("Fetching all delays for scoring key alignment...")
    delays = execute_query('SELECT id, reason_text, ai_analysis_json FROM delays', fetch=True)
    
    updated_count = 0
    for d in delays:
        analysis = d['ai_analysis_json']
        if not analysis:
            continue
            
        print(f"Processing Delay ID {d['id']}...")
        try:
            # 1. Ensure summary exists (or use existing)
            interpretation = analysis.get('ai_interpretation', {})
            summary = interpretation.get('summary', 'NO_INTERPRETATION_GENERATED')
            
            if summary == 'NO_INTERPRETATION_GENERATED' or not summary:
                print("  - Generating missing summary...")
                res = analyze_excuse_with_ai(d['reason_text'])
                summary = res.get('summary', 'AI interpretation generated.')
                
                if 'ai_interpretation' not in analysis:
                    analysis['ai_interpretation'] = {}
                analysis['ai_interpretation']['summary'] = summary
            
            # 2. Align scoring keys for live site display coverage (ALWAYS RUN)
            # Live site template expects 'pressure' and 'confidence' at top level
            feat = analysis.get('feature_vector', {})
            analysis['pressure'] = feat.get('deadline_pressure', 0.0)
            analysis['confidence'] = analysis.get('confidence_score', 0.0)
            
            # Save back to DB
            execute_query('UPDATE delays SET ai_analysis_json = %s WHERE id = %s', 
                         (json.dumps(analysis), d['id']), fetch=False)
            print(f"  - [OK] Aligned keys for Delay {d['id']}")
            updated_count += 1
        except Exception as e:
            print(f"  - [FAIL] Error updating Delay {d['id']}: {e}")
                
    print(f"\nCompleted. Total updated: {updated_count}")

if __name__ == "__main__":
    backfill_summaries()
