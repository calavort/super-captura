"""Open two real copies of app.py in the SAME isolated installation."""
import argparse
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from atualizacao.atualizador import APP_FILES, InstanceLock, running_instances, write_json

VALIDATE = r"""
const {chromium} = require('playwright');
(async () => {
    const pages = [];
    for (const endpoint of process.argv.slice(1)) {
        let browser;
        for (let attempt=0; attempt<60; attempt++) {
            try { browser = await chromium.connectOverCDP(endpoint,{noDefaults:true}); break; }
            catch { await new Promise(resolve=>setTimeout(resolve,200)); }
        }
        if (!browser) throw Error('App did not open: '+endpoint);
        const page=browser.contexts()[0].pages()[0];
        await page.waitForFunction(()=>typeof pyBridge !== 'undefined' && pyBridge);
        pages.push(page);
    }
    for (let i=0; i<pages.length; i++) {
        await pages[i].evaluate(index=>{
            scheduleClipboardSync=()=>{}; syncClipboardNow=()=>{};
            const c=document.createElement('canvas');c.width=400+index*100;c.height=250;
            const context=c.getContext('2d');context.fillStyle=index?'#107C41':'#4472C4';
            context.fillRect(0,0,c.width,c.height);
            loadImageData(c.toDataURL(),false,false);
        },i);
        await pages[i].waitForFunction(width=>bgImage?.naturalWidth===width,400+i*100);
        await pages[i].evaluate(index=>{
            annotations.push({type:'Texto',x:20,y:20,w:220,h:40,text:'Janela '+(index+1),color:'#FFFFFF',font:24});
            redraw();
        },i);
    }
    for (let i=0;i<pages.length;i++) {
        const data=await pages[i].evaluate(()=>({width:bgImage.naturalWidth,text:annotations[0].text}));
        if(data.width!==400+i*100 || data.text!=='Janela '+(i+1)) throw Error(JSON.stringify(data));
        console.log('OK: janela independente '+JSON.stringify(data));
    }
    await pages[0].screenshot({path:process.env.SC_TEST_SCREENSHOT});
    try { await pages[0].evaluate(()=>pyBridge.closeWindow()); }
    catch(e) { if(!String(e).includes('closed')) throw e; }
    await pages[1].evaluate(()=>{annotations[0].text='Segunda janela continua editavel';redraw()});
    if(await pages[1].evaluate(()=>annotations[0].text)!=='Segunda janela continua editavel') throw Error('Second window was affected');
    console.log('OK: fechar a primeira janela preserva a segunda');
    try { await pages[1].evaluate(()=>pyBridge.closeWindow()); }
    catch(e) { if(!String(e).includes('closed')) throw e; }
})().then(()=>process.exit(0)).catch(error=>{console.error(error);process.exit(1)});
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--node', required=True)
    parser.add_argument('--node-modules', required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='super-captura-multiple-') as temporary:
        folder = Path(temporary)
        for name in APP_FILES:
            target = folder / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        write_json(folder / 'configuracoes.json', {'auto_copy':False, 'user':{'name':'Teste multiplas janelas'}})
        processes, endpoints = [], []
        try:
            for _ in range(2):
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1',0))
                    port = sock.getsockname()[1]
                endpoints.append(f'http://127.0.0.1:{port}')
                env = dict(os.environ, QTWEBENGINE_REMOTE_DEBUGGING=f'127.0.0.1:{port}')
                processes.append(subprocess.Popen([sys.executable,str(folder/'app.py')],cwd=folder,env=env,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
            output = ROOT/'dist'/'validacao-multiplas-janelas.png'
            output.parent.mkdir(exist_ok=True)
            env = dict(os.environ,NODE_PATH=args.node_modules,SC_TEST_SCREENSHOT=str(output))
            result = subprocess.run([args.node,'-e',VALIDATE,*endpoints],env=env,timeout=45,capture_output=True,text=True)
            print(result.stdout)
            assert result.returncode == 0, result.stderr
            for process in processes:
                assert process.wait(timeout=10) == 0
            assert running_instances(folder) == 0
            installer = InstanceLock(folder)
            assert installer.acquire()
            installer.release()
            print('OK: app.py aberto duas vezes na mesma pasta; instalador liberado ao fechar ambas')
        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)


if __name__ == '__main__':
    main()
