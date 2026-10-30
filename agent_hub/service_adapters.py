"""Documented read-only service adapters; credentials stay in runtime environment.

An available interface/configuration is never an authentication or live-call claim.
No publishing, deployment, purchases, messages or other consequential method exists.
"""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid

from .security import redact


class IntegrationUnavailable(RuntimeError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None


class _ReadHTTP:
    provider='UNCONFIGURED'
    base=''
    max_bytes=1_048_576
    def __init__(self,token_env,timeout=20,transport=None):
        if not isinstance(token_env,str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,99}',token_env):
            raise ValueError('Use a non-secret environment-variable name for credentials')
        if not isinstance(timeout,(int,float)) or isinstance(timeout,bool) or not 1<=timeout<=60:
            raise ValueError('Read timeout must be 1..60 seconds')
        self.token_env=token_env;self.timeout=timeout;self.transport=transport
        self._authenticated=False

    def _token(self):
        return os.environ.get(self.token_env)

    def probe(self):
        configured=bool(self._token())
        return {'provider':self.provider,'available':True,'configured':configured,
                'authenticated':self._authenticated if configured else False,
                'status':'AUTHENTICATED' if self._authenticated else 'AVAILABLE_NOT_CONNECTED',
                'reason':None if configured else 'Credential environment binding not configured; no authentication claim',
                'read_only':True}

    def _headers(self):
        headers={'Accept':'application/json','User-Agent':'MasterAgentSystem/0.6-read-only'}
        token=self._token()
        if token:headers['Authorization']='Bearer '+token
        return headers

    def _get(self,path,requires_token=False):
        if requires_token and not self._token():
            raise IntegrationUnavailable(self.provider+' authentication is not configured')
        url=self.base+path
        headers=self._headers()
        try:
            if self.transport:
                # Only a trusted host injects transport; a package/config cannot load code.
                response=self.transport('GET',url,headers,self.timeout)
                if not isinstance(response,dict) or type(response.get('status')) is not int:
                    raise ValueError('Read transport must return HTTP status and body')
                status=response['status'];body=response.get('body',b'')
                if isinstance(body,(dict,list)):body=json.dumps(body).encode()
                elif isinstance(body,str):body=body.encode()
                if not isinstance(body,bytes):raise ValueError('Read response body must be bytes or JSON')
            else:
                opener=urllib.request.build_opener(_NoRedirect()) # retain inherited proxy/TLS/CA
                request=urllib.request.Request(url,headers=headers,method='GET')
                with opener.open(request,timeout=self.timeout) as response:
                    status=response.status;body=response.read(self.max_bytes+1)
            if len(body)>self.max_bytes:raise ValueError('Provider response exceeds bounded read limit')
            if not 200<=status<300:raise IntegrationUnavailable(self.provider+' read failed with HTTP '+str(status))
            result=json.loads(body.decode('utf-8'))
        except urllib.error.HTTPError as exc:
            raise IntegrationUnavailable(self.provider+' read failed with HTTP '+str(exc.code)) from None
        except urllib.error.URLError:
            raise IntegrationUnavailable(self.provider+' read transport unavailable; inspect authorized network/configuration') from None
        except (OSError,RuntimeError) as exc:
            raise IntegrationUnavailable(self.provider+' read transport failed ('+type(exc).__name__+'); inspect authorized configuration') from None
        return {'ok':True,'authenticated':bool(self._authenticated),'reference':url,
                'data':redact(result),'provider':self.provider,'operation_kind':'read',
                'evidence_kind':'SIMULATED' if self.transport else 'LIVE_HTTP'}


class GitHubReadAdapter(_ReadHTTP):
    """GitHub REST: /user, /repos/{owner}/{repo}, contents and repository search.

    Official contracts: https://docs.github.com/en/rest/users/users#get-the-authenticated-user
    https://docs.github.com/en/rest/repos/repos#get-a-repository
    https://docs.github.com/en/rest/repos/contents#get-repository-content
    https://docs.github.com/en/rest/search/search#search-repositories
    """
    provider='GitHub'
    base='https://api.github.com'
    operations=[{'name':name,'kind':'read'} for name in
                ['github.user','github.repository','github.contents','github.search_repositories','github.commits','github.issues','github.pull_requests']]
    def __init__(self,token_env='GITHUB_TOKEN',timeout=20,transport=None):
        super().__init__(token_env,timeout,transport)

    def _headers(self):
        return dict(super()._headers(),Accept='application/vnd.github+json')

    @staticmethod
    def _segment(value,label):
        if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',value) or value in {'.','..'}:
            raise ValueError('Invalid GitHub '+label)
        return urllib.parse.quote(value,safe='')

    def __call__(self,operation,arguments,context=None):
        if not isinstance(arguments,dict):raise ValueError('GitHub read arguments must be an object')
        if operation=='github.user':
            if arguments:raise ValueError('Authenticated user read takes no arbitrary query fields')
            result=self._get('/user',True)
            if not isinstance(result['data'],dict) or not result['data'].get('login'):
                raise ValueError('Authenticated user response missing actual user evidence')
            self._authenticated=True;result['authenticated']=True
            result['granted_operations']=[o['name'] for o in self.operations]
            # The adapter itself exposes only GET reads. A token may have broader scopes,
            # but neither a successful /user nor this adapter grants write capabilities.
            return result
        if operation in {'github.repository','github.contents'}:
            allowed={'owner','repo'}|({'path','ref'} if operation=='github.contents' else set())
            if set(arguments)-allowed:raise ValueError('Unsupported GitHub read fields')
            path='/repos/'+self._segment(arguments.get('owner'),'owner')+'/'+self._segment(arguments.get('repo'),'repository')
            if operation=='github.contents':
                relative=arguments.get('path','')
                if not isinstance(relative,str) or relative.startswith('/') or '\\' in relative or '..' in relative.split('/') or any(ord(c)<32 for c in relative):
                    raise ValueError('Unsafe repository content path')
                path+='/contents/'+urllib.parse.quote(relative,safe='/')
                ref=arguments.get('ref')
                if ref is not None:
                    if not isinstance(ref,str) or not ref.strip() or len(ref)>200:raise ValueError('Invalid repository ref')
                    path+='?'+urllib.parse.urlencode({'ref':ref})
            return self._get(path)
        if operation in {'github.commits','github.issues','github.pull_requests'}:
            if set(arguments)-{'owner','repo','limit','state'}:raise ValueError('Unsupported GitHub history/read fields')
            limit=arguments.get('limit',10)
            if type(limit) is not int or not 1<=limit<=30:raise ValueError('Read limit must be 1..30')
            path='/repos/'+self._segment(arguments.get('owner'),'owner')+'/'+self._segment(arguments.get('repo'),'repo')
            suffix={'github.commits':'commits','github.issues':'issues','github.pull_requests':'pulls'}[operation]
            params={'per_page':limit}
            if operation!='github.commits':
                state=arguments.get('state','open')
                if state not in {'open','closed','all'}:raise ValueError('Invalid issue/PR state')
                params['state']=state
            elif 'state' in arguments:raise ValueError('Commit reads have no issue state')
            return self._get(path+'/'+suffix+'?'+urllib.parse.urlencode(params))
        if operation=='github.search_repositories':
            if set(arguments)-{'query','limit'}:raise ValueError('Unsupported GitHub repository-search fields')
            query=arguments.get('query');limit=arguments.get('limit',5)
            if not isinstance(query,str) or not query.strip() or len(query)>500 or redact(query)!=query:
                raise ValueError('Use a bounded public query with no credentials')
            if type(limit) is not int or not 1<=limit<=20:raise ValueError('Repository search limit must be 1..20')
            return self._get('/search/repositories?'+urllib.parse.urlencode({'q':query,'per_page':limit}))
        raise PermissionError('GitHub adapter exposes documented read-only operations only')

    def search(self,query,limit=5):
        response=self('github.search_repositories',{'query':query,'limit':limit})
        data=response['data']
        if not isinstance(data,dict) or not isinstance(data.get('items'),list):raise ValueError('Unexpected GitHub repository-search response')
        return {'provider':'GitHub repository search','scope':'REPOSITORY_METADATA_NOT_GENERAL_WEB',
                'reference':response['reference'],'evidence_kind':response['evidence_kind'],
                'results':[{'url':item.get('html_url'),'title':item.get('full_name'),
                            'snippet':item.get('description') or ''} for item in data['items'][:limit]]}


class NotionReadAdapter(_ReadHTTP):
    """Documented Notion GET /v1/users/me and /v1/pages/{id}.

    https://developers.notion.com/reference/get-self
    https://developers.notion.com/reference/retrieve-a-page
    Configure the account's supported documented Notion-Version explicitly; no guessed
    latest API version or credentials are bundled. This is not a Vault write/sync adapter.
    """
    provider='Notion'
    base='https://api.notion.com'
    operations=[{'name':'notion.user','kind':'read'},{'name':'notion.page','kind':'read'}]
    def __init__(self,version=None,token_env='NOTION_API_TOKEN',timeout=20,transport=None):
        super().__init__(token_env,timeout,transport)
        if version is not None and (not isinstance(version,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',version)):
            raise ValueError('Notion version must be an explicitly documented YYYY-MM-DD version')
        self.version=version

    def probe(self):
        result=super().probe()
        if not self.version:result.update(configured=False,authenticated=False,status='AVAILABLE_NOT_CONNECTED',reason='Explicit supported Notion-Version not configured')
        return result

    def _headers(self):
        if not self.version:raise IntegrationUnavailable('Notion-Version is not configured')
        return dict(super()._headers(),**{'Notion-Version':self.version})

    def __call__(self,operation,arguments,context=None):
        if not isinstance(arguments,dict):raise ValueError('Notion read arguments must be an object')
        if operation=='notion.user':
            if arguments:raise ValueError('Notion user read takes no extra fields')
            result=self._get('/v1/users/me',True)
            if not isinstance(result['data'],dict) or not result['data'].get('id'):raise ValueError('Actual authenticated Notion user ID is required')
            self._authenticated=True;result['authenticated']=True
            result['granted_operations']=[o['name'] for o in self.operations]
            return result
        if operation=='notion.page':
            if set(arguments)!={'page_id'}:raise ValueError('Notion page read requires only page_id')
            try:page=str(uuid.UUID(arguments['page_id']))
            except (ValueError,TypeError,AttributeError):raise ValueError('Notion page ID must be a UUID') from None
            return self._get('/v1/pages/'+page,True)
        raise PermissionError('Notion adapter exposes documented read-only operations only')


class NativeReadAdapter:
    """Trusted host callback for actually discovered native read tools.

    Figma/Drive/Higgsfield/other candidate names do not create transports/endpoints.
    The host passes actual tool names and the real callable; configuration cannot
    dynamically import or execute third-party code. No implicit authentication claim.
    """
    def __init__(self,provider,operations,invoke,evidence_kind='LIVE_NATIVE_TOOL'):
        if not isinstance(provider,str) or not provider.strip():raise ValueError('Actual provider name required')
        if not isinstance(operations,list) or not operations or any(not isinstance(o,dict) or o.get('kind')!='read' or not isinstance(o.get('name'),str) for o in operations):
            raise ValueError('Supply actual discovered read-only operations')
        if not callable(invoke):raise IntegrationUnavailable('Native tool bridge is not configured')
        if evidence_kind not in {'LIVE_NATIVE_TOOL','SIMULATED'}:raise ValueError('Native read evidence must distinguish live versus simulated calls')
        self.provider=provider;self.operations=operations;self.invoke=invoke
        self.evidence_kind=evidence_kind
    def probe(self):
        return {'provider':self.provider,'available':True,'configured':True,'authenticated':None,
                'status':'AVAILABLE_NOT_CONNECTED','reason':'Actual read/auth test required','read_only':True}
    def __call__(self,operation,arguments,context=None):
        if operation not in {o['name'] for o in self.operations}:raise PermissionError('Native operation was not discovered as a read')
        if not isinstance(arguments,dict) or redact(arguments)!=arguments:raise ValueError('Native read arguments cannot contain credentials')
        result=self.invoke(operation,arguments,context or {})
        if not isinstance(result,dict) or result.get('ok') is not True or not result.get('reference'):
            raise IntegrationUnavailable('Native read did not return an actual successful reference')
        return dict(redact(result),evidence_kind=self.evidence_kind,operation_kind='read')
