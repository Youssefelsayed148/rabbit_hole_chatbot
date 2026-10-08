"""Summarize local metadata-only usage logs using verified standard OpenAI USD rates."""
import argparse
from collections import Counter
import json
from pathlib import Path

SOURCES = {
    'gpt-4.1-mini': 'https://developers.openai.com/api/docs/models/gpt-4.1-mini',
    'text-embedding-3-large': 'https://developers.openai.com/api/docs/models/text-embedding-3-large',
}


def summarize(path):
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line]
    requests = {row['call_id']: row for row in rows if row['event'] == 'request'}
    responses = [row for row in rows if row['event'] == 'response']
    counts = Counter(row['endpoint'] for row in requests.values())
    tokens = Counter()
    cost = 0.0
    for response in responses:
        request = requests[response['call_id']]
        if response['status'] != 200:
            continue
        inp, out, cached = (response[name] for name in ('prompt_tokens', 'completion_tokens', 'cached_tokens'))
        if request['model'] == 'text-embedding-3-large':
            tokens['embedding_input'] += inp
            cost += inp * 0.13 / 1_000_000
        elif request['model'] == 'gpt-4.1-mini':
            tokens['chat_input'] += inp
            tokens['chat_cached_input'] += cached
            tokens['chat_output'] += out
            cost += ((inp - cached) * 0.40 + cached * 0.10 + out * 1.60) / 1_000_000
        else:
            raise ValueError('No verified price for requested model')
    successes = sum(row['status'] == 200 for row in responses)
    return {'requests': len(requests), 'successful_responses': successes,
            'unsuccessful_or_unanswered_attempts': len(requests) - successes,
            'embedding_requests': counts['/v1/embeddings'],
            'chat_requests': counts['/v1/chat/completions'],
            'tokens': dict(tokens), 'estimated_usd': round(cost, 8)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    phases = {name: summarize(args.root / path) for name, path in {
        'api-real startup': 'startup-usage.jsonl',
        'real-smoke': 'smoke/openai-usage.jsonl',
        'quality': 'quality-usage.jsonl',
    }.items()}
    total = Counter()
    tokens = Counter()
    for phase in phases.values():
        total.update({key: value for key, value in phase.items() if key != 'tokens'})
        tokens.update(phase['tokens'])
    total['estimated_usd'] = round(total['estimated_usd'], 8)
    report = {'prices_verified_on': '2026-10-06', 'currency': 'USD', 'rates_per_million_tokens': {
        'gpt-4.1-mini': {'input': 0.40, 'cached_input': 0.10, 'output': 1.60},
        'text-embedding-3-large': {'input': 0.13}}, 'pricing_sources': SOURCES,
        'phases': phases, 'total': {**total, 'tokens': dict(tokens)}}
    (args.root / 'usage-summary.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    lines = ['# Real Docker verification usage', '', 'Measured HTTP attempts and response token usage; no prompts or credentials logged.', '',
             '| Phase | API calls | Embeddings | Chat / judge | Approx. USD |', '|---|---:|---:|---:|---:|']
    for phase, row in phases.items():
        lines.append(f"| {phase} | {row['requests']} | {row['embedding_requests']} | {row['chat_requests']} | ${row['estimated_usd']:.6f} |")
    lines += [f"| Total | {total['requests']} | {total['embedding_requests']} | {total['chat_requests']} | ${total['estimated_usd']:.6f} |", '',
              'Token totals: ' + json.dumps(dict(tokens)), '',
              f"Unsuccessful/unanswered HTTP attempts: {total['unsuccessful_or_unanswered_attempts']}.", '',
              'Estimate uses standard public rates and reported cached tokens; account credits, taxes and billing adjustments are excluded.', '',
              'Rates verified 2026-10-06: [GPT-4.1 mini](' + SOURCES['gpt-4.1-mini'] + '), [text-embedding-3-large](' + SOURCES['text-embedding-3-large'] + ').', '']
    (args.root / 'usage-summary.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(report['total'], indent=2))


if __name__ == '__main__':
    main()
