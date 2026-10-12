"""Non-destructive structural and controller simulations. Does not change Windows."""
import ast,collections,copy,json,sys,types,unittest
from pathlib import Path

# Linux CI: provide winreg constants for the pure controller/manifest tests.
if sys.platform!='win32':
    w=types.ModuleType('winreg')
    for i,name in enumerate(('HKEY_CURRENT_USER','HKEY_LOCAL_MACHINE','HKEY_CLASSES_ROOT','KEY_READ','KEY_WRITE','KEY_SET_VALUE','KEY_WOW64_64KEY','KEY_WOW64_32KEY','REG_SZ','REG_EXPAND_SZ','REG_DWORD','REG_QWORD','REG_BINARY','REG_MULTI_SZ')):setattr(w,name,i+1)
    sys.modules['winreg']=w
from bbys_controller import Controller,aggregate
from bbys_registry import token

ROOT=Path(__file__).parent
FEATURES=json.loads((ROOT/'bbys_features.json').read_text(encoding='utf-8'))
class Backend:
    def __init__(self,app_dir):self.app_dir=Path(app_dir);self.values={};self.calls=[];self.uwp=True;self.bootstamp=1000
    def expand_ops(self,ops):return list(ops)
    def desired(self,op):return op.get('data')
    def read(self,op):
        if op['kind']=='uwp_policy_check':return {'effective':self.uwp}
        if op['kind']=='file_exists':return False
        return self.values.get(token(op),None)
    def matches(self,op,value):
        if op['kind']=='uwp_policy_check':return value.get('effective') is True
        return value==self.desired(op)
    def apply(self,op,value):self.calls.append((op['kind'],op.get('name',''),value));self.values[token(op)]=value
    def refresh(self):pass
    def boot_marker(self):return self.bootstamp

class Validation(unittest.TestCase):
    def test_compiles(self):
        for path in ROOT.glob('*.py'):ast.parse(path.read_text(encoding='utf-8'),filename=path.name)
    def test_every_feature_has_title_and_operation(self):
        self.assertEqual(len(FEATURES),31)
        for fid,f in FEATURES.items():
            with self.subTest(fid=fid):
                self.assertTrue(f['title']);self.assertTrue(f['ops'])
                self.assertTrue(all('kind' in op for op in f['ops']))
    def test_uwp_has_effective_probe(self):
        ops=FEATURES['disable_uwp_background']['ops']
        self.assertEqual(len(ops),3)
        self.assertTrue(any(x['kind']=='uwp_policy_check' and x['check_only'] for x in ops))
    def test_enable_and_exact_revert(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            fake=Backend(d);op={'kind':'registry','key':'HKCU\\Software\\Example','name':'Enabled','data':1}
            fake.values[token(op)]=7
            ctrl=Controller(fake,{'x':{'ops':[op]}},Path(d)/'state.json')
            self.assertEqual(ctrl.set_feature('x',True)['status'],'enabled')
            self.assertEqual(fake.values[token(op)],1)
            self.assertIn('x',ctrl.state['features'])
            ctrl.set_feature('x',False)
            self.assertEqual(fake.values[token(op)],7)
            self.assertNotIn('x',ctrl.state['features'])
    def test_shared_ownership(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            b=Backend(d);op={'kind':'registry','key':'HKCU\\X','name':'Y','data':1}
            b.values[token(op)]=0
            ctl=Controller(b,{'a':{'ops':[op]},'b':{'ops':[op]}},Path(d)/'x.json')
            ctl.set_feature('a',True);ctl.set_feature('b',True)
            ctl.set_feature('a',False);self.assertEqual(b.values[token(op)],1)
            ctl.set_feature('b',False);self.assertEqual(b.values[token(op)],0)
    def test_uwp_probe_cannot_be_falsely_green(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            b=Backend(d);b.uwp=False
            ctrl=Controller(b,{'u':{'ops':[{'kind':'registry','key':'HKCU\\Test','name':'v','data':1},
                                             {'kind':'uwp_policy_check','name':'effective','data':True,'check_only':True,'post_apply':True}]}},Path(d)/'state.json')
            result=ctrl.set_feature('u',True)
            self.assertEqual(result['status'],'partial')
            self.assertTrue(any(x[0]=='registry' for x in b.calls))
            self.assertFalse(any(x[0]=='uwp_policy_check' for x in b.calls))
    def test_reboot_required_prevents_false_success(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            b=Backend(d)
            f={'disable_uwp_background':{'ops':[{'kind':'registry','key':'HKCU\\Test','name':'v','data':1},
                            {'kind':'uwp_policy_check','name':'effective','data':True,'check_only':True,'post_apply':True}]}}
            ctl=Controller(b,f,Path(d)/'state.json')
            self.assertEqual(ctl.set_feature('disable_uwp_background',True)['status'],'partial')
            self.assertIn('disable_uwp_background',ctl.state['pending_restart'])
            b.bootstamp=1350
            self.assertEqual(ctl.check('disable_uwp_background')['status'],'enabled')
            self.assertNotIn('disable_uwp_background',ctl.state['pending_restart'])
    def test_uwp_policy_edition_and_override_checks(self):
        from unittest.mock import patch
        import bbys_system
        import bbys_registry as reg
        backend=bbys_system.WindowsBackend(ROOT)
        baseline={
          'EditionID':{'data':'Professional','exists':True},
          'GlobalUserDisabled':{'data':1,'type':reg.TYPES['REG_DWORD'],'exists':True},
          'LetAppsRunInBackground':{'data':2,'type':reg.TYPES['REG_DWORD'],'exists':True}}
        def reader(key,name):return baseline.get(name,{'exists':False})
        with patch.object(bbys_system,'sys_windows_build',return_value=26200),patch.object(reg,'read',side_effect=reader):
            self.assertTrue(backend.uwp_policy_status()['effective'])
            baseline['EditionID']={'data':'Core','exists':True}
            self.assertFalse(backend.uwp_policy_status()['effective'])
            baseline['EditionID']={'data':'Professional','exists':True}
            baseline['LetAppsRunInBackground_ForceAllowTheseApps']={'data':'Contoso.App_123','exists':True}
            self.assertFalse(backend.uwp_policy_status()['effective'])
            self.assertTrue(backend.uwp_policy_status()['exceptions'])
            del baseline['LetAppsRunInBackground_ForceAllowTheseApps']
            baseline['LetAppsRunInBackground']={'data':1,'type':reg.TYPES['REG_DWORD'],'exists':True}
            self.assertFalse(backend.uwp_policy_status()['effective'])
    def test_missing_source_prevent_partial_execution(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            b=Backend(d);op={'kind':'registry','key':'HKCU\\Test','name':'icon','data':'${APP}\\source\\x.ico'}
            ctl=Controller(b,{'x':{'ops':[op]}},Path(d)/'state.json')
            with self.assertRaisesRegex(RuntimeError,'source'):ctl.set_feature('x',True)
            self.assertFalse(b.calls);self.assertFalse(ctl.state['features'])
    def test_build_script_checks_external_assets(self):
        script=(ROOT/'build_bbys.py').read_text(encoding='utf-8')
        self.assertIn("if not (ROOT/'source').is_dir()",script)
    def test_aggregate(self):
        self.assertEqual(aggregate([{'status':'match'}]),'enabled')
        self.assertEqual(aggregate([{'status':'match'},{'status':'unknown'}],True),'partial')
        self.assertEqual(aggregate([{'status':'na'}]),'unknown')

if __name__=='__main__':unittest.main(verbosity=2)
