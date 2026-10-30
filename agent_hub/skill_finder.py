"""Adapter to the uploaded instruction-only Skill Finder. Discovery never installs."""
import json
from urllib.parse import urlencode, urlparse

from .legacy import required


class SkillFinderAdapter:
    endpoint = 'https://claude-plugins.dev/api/skills'

    def __init__(self, transport=None):
        # A host may inject an explicitly authorized WebFetch/HTTP implementation.
        # No network call or package-manager subprocess is enabled by default.
        self.transport = transport

    def search(self, keywords):
        required(keywords, 'Capability keywords')
        if len(keywords) > 500:
            raise ValueError('Capability query is too long')
        url = self.endpoint + '?' + urlencode({'q': keywords})
        if self.transport is None:
            return {'status': 'REQUIRES_CONFIGURATION', 'query_url': url, 'candidates': [],
                    'note': 'Instruction-only ZIP inspected. Live endpoint and installer are unverified; supply an authorized transport.'}
        document = self.transport(url)
        if isinstance(document, str):
            document = json.loads(document)
        if not isinstance(document, dict) or not isinstance(document.get('skills'), list):
            raise ValueError('Skill Finder response does not match its documented schema')
        candidates = []
        for item in document['skills'][:100]:
            if not isinstance(item, dict):
                raise ValueError('Malformed Skill Finder candidate')
            for key in ['name', 'namespace', 'description']:
                required(item.get(key), 'Candidate ' + key)
            metadata = item.get('metadata', {})
            if not isinstance(metadata, dict):
                raise ValueError('Malformed candidate metadata')
            raw = metadata.get('rawFileUrl')
            if raw and urlparse(raw).scheme != 'https':
                raise ValueError('Skill source requires HTTPS')
            candidates.append({'name': item['name'], 'namespace': item['namespace'],
                'description': item['description'], 'raw_file_url': raw,
                'security_status': 'QUARANTINED', 'installed': False,
                'review_required': ['compatibility', 'dependencies', 'permissions', 'license', 'security', 'tests', 'independent QA']})
        return {'status': 'CANDIDATES_ONLY', 'query_url': url, 'candidates': candidates}

    def install(self, candidate):
        raise PermissionError('Automatic Skill Finder installation is disabled; inspect, test and independently review a staged candidate first')
