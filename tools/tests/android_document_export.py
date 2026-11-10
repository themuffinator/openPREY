#!/usr/bin/env python3
"""Exercise production save/log export against controlled Android document providers."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from android_private_export import verify_archive

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
'android/net/Uri.java': r'''
package android.net;
public final class Uri {
    private final String scheme;
    public Uri(String scheme){this.scheme=scheme;}
    public String getScheme(){return scheme;}
}
''',
'android/os/CancellationSignal.java': r'''
package android.os;
public final class CancellationSignal {
    private volatile boolean cancelled;
    public void cancel(){cancelled=true;}
    public boolean isCanceled(){return cancelled;}
}
''',
'android/os/OperationCanceledException.java': r'''
package android.os;
public class OperationCanceledException extends RuntimeException {}
''',
'android/os/ParcelFileDescriptor.java': r'''
package android.os;
import java.io.*;
public final class ParcelFileDescriptor implements Closeable {
    public final OutputStream output;
    public boolean failCreate;
    public int closes;
    public ParcelFileDescriptor(OutputStream output){this.output=output;}
    public void close()throws IOException {++closes;output.close();}
    public static final class AutoCloseOutputStream extends OutputStream {
        private final ParcelFileDescriptor descriptor;
        public AutoCloseOutputStream(ParcelFileDescriptor descriptor) {
            this.descriptor=descriptor;
            if(descriptor.failCreate)throw new IllegalStateException("provider descriptor invalid");
        }
        public void write(int value)throws IOException {descriptor.output.write(value);}
        public void write(byte[] bytes,int offset,int count)throws IOException {descriptor.output.write(bytes,offset,count);}
        public void flush()throws IOException {descriptor.output.flush();}
        public void close()throws IOException {descriptor.close();}
    }
}
''',
'android/content/ContentResolver.java': r'''
package android.content;
import android.net.Uri;
import android.os.*;
import java.io.FileNotFoundException;
public abstract class ContentResolver {
    public abstract ParcelFileDescriptor openFileDescriptor(Uri uri,String mode,CancellationSignal signal)throws FileNotFoundException;
}
''',
'android/content/Context.java': r'''
package android.content;
import java.io.File;
public final class Context {
    public Context application=this;
    public File files,cache;
    public ContentResolver resolver;
    public Context getApplicationContext(){return application;}
    private void check(){if(application!=this)throw new AssertionError("export retained Activity context");}
    public File getFilesDir(){check();return files;}
    public File getCacheDir(){check();return cache;}
    public ContentResolver getContentResolver(){check();return resolver;}
}
''',
'com/darkmatter/openq4/DocumentExportTest.java': r'''
package com.darkmatter.openq4;
import android.content.*;
import android.net.Uri;
import android.os.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public final class DocumentExportTest {
    static final Uri DESTINATION=new Uri("content");
    static void require(boolean value,String why){if(!value)throw new AssertionError(why);}
    interface Action {void run()throws Exception;}
    static void failed(PrivateExport.Code code,Action action)throws Exception {
        try{action.run();throw new AssertionError("accepted "+code);}
        catch(PrivateExport.Failure error){require(error.code==code,"wrong error "+error);}
    }
    static void cancelled(Action action)throws Exception {
        try{action.run();throw new AssertionError("ignored cancellation");}catch(InterruptedIOException expected){}
    }
    static void available()throws Exception {Object owner=StorageSession.INSTANCE.beginSetup();StorageSession.INSTANCE.endSetup(owner);}
    static void clean(Context app)throws Exception {
        available();Path work=app.cache.toPath().resolve("openq4-exports");
        if(Files.exists(work))try(var files=Files.list(work)){require(files.findAny().isEmpty(),"private export left behind");}
    }
    static final class Progress implements SetupTask.Reporter {
        final List<SetupTask.Progress> updates=new ArrayList<>();
        volatile boolean stop;
        SetupTask.Phase stopAt;
        public boolean cancelled(){return stop;}
        public boolean update(SetupTask.Phase phase,String name,int completed,int files,long bytes,long total) {
            updates.add(new SetupTask.Progress(phase,name,completed,files,bytes,total));
            if(phase==stopAt)stop=true;return !stop;
        }
    }
    static class Output extends OutputStream {
        final ByteArrayOutputStream bytes=new ByteArrayOutputStream();
        boolean failWrite,failFlush,failClose,closed;
        public void write(int value)throws IOException {if(failWrite)throw new IOException("write rejected");bytes.write(value);}
        public void write(byte[] data,int offset,int count)throws IOException {
            if(failWrite){bytes.write(data,offset,Math.min(5,count));throw new IOException("provider disconnected");}
            bytes.write(data,offset,count);
        }
        public void flush()throws IOException {if(failFlush)throw new IOException("flush failed");}
        public void close()throws IOException {closed=true;if(failClose)throw new IOException("close failed");}
    }
    static class Provider extends ContentResolver {
        OutputStream output=new Output();
        ParcelFileDescriptor last;
        CancellationSignal signal;
        int opens;
        boolean deny,missing,nullDescriptor,failCreate;
        Runnable opening;
        public ParcelFileDescriptor openFileDescriptor(Uri uri,String mode,CancellationSignal cancellation)throws FileNotFoundException {
            require(uri==DESTINATION && mode.equals("wt"),"wrong document or access mode");
            ++opens;signal=cancellation;
            if(deny)throw new SecurityException("revoked grant");
            if(missing)throw new FileNotFoundException("removed destination");
            if(opening!=null)opening.run();
            if(nullDescriptor)return null;
            last=new ParcelFileDescriptor(output);last.failCreate=failCreate;return last;
        }
    }
    static Provider provider(Context app){Provider next=new Provider();app.resolver=next;return next;}
    static DocumentExport work(Context activity){return new DocumentExport(activity,DESTINATION,PrivateExport.Kind.SAVES);}
    static void drain(BlockingQueue<Runnable> queue,SetupTask<?> task)throws Exception {
        long end=System.nanoTime()+TimeUnit.SECONDS.toNanos(10);
        while(task.state().busy() && System.nanoTime()<end){Runnable callback=queue.poll(50,TimeUnit.MILLISECONDS);if(callback!=null)callback.run();}
        require(!task.state().busy(),"worker never completed");
    }
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]);Context app=new Context();app.files=root.resolve("private").toFile();app.cache=root.resolve("cache").toFile();
        Context activity=new Context();activity.application=app;
        Path save=app.files.toPath().resolve("saves/baseoq4/savegames/Test.save");Files.createDirectories(save.getParent());
        byte[] original=new byte[190000];new Random(77).nextBytes(original);Files.write(save,original);
        Provider first=provider(app);Progress progress=new Progress();DocumentExport.Result result=work(activity).run(progress);
        Output output=(Output)first.output;
        require(result.files==1 && result.kind==PrivateExport.Kind.SAVES && result.bytes==output.bytes.size(),"wrong export summary");
        require(first.opens==1 && first.last.closes==1 && output.closed,"destination descriptor leaked");
        require(progress.updates.stream().anyMatch(p->p.phase==SetupTask.Phase.PACKING_EXPORT) &&
                progress.updates.stream().anyMatch(p->p.phase==SetupTask.Phase.EXPORTING && p.bytes==p.totalBytes),"missing phase/complete progress");
        Files.write(root.resolve("provider.zip"),output.bytes.toByteArray());clean(app);
        Provider invalid=provider(app);
        failed(PrivateExport.Code.OUTPUT_UNAVAILABLE,()->new DocumentExport(activity,new Uri("file"),PrivateExport.Kind.SAVES).run(new Progress()));
        require(invalid.opens==0,"opened ungranted path");clean(app);
        for(int failure=0;failure<4;++failure) {
            Provider p=provider(app);p.deny=failure==0;p.missing=failure==1;p.nullDescriptor=failure==2;p.failCreate=failure==3;
            failed(PrivateExport.Code.OUTPUT_UNAVAILABLE,()->work(activity).run(new Progress()));
            if(p.last!=null)require(p.last.closes==1,"invalid descriptor leaked");clean(app);
        }
        for(int failure=0;failure<3;++failure) {
            Provider p=provider(app);Output out=(Output)p.output;out.failWrite=failure==0;out.failFlush=failure==1;out.failClose=failure==2;
            failed(PrivateExport.Code.WRITE_FAILED,()->work(activity).run(new Progress()));
            require(p.last.closes==1 && out.closed,"failed stream not closed exactly once");
            require(out.bytes.size()>0,"fixture did not leave the expected partial/uncertain document");clean(app);
        }
        Provider before=provider(app);DocumentExport stopped=work(activity);stopped.cancel();cancelled(()->stopped.run(new Progress()));
        require(before.opens==0,"pre-cancel opened destination");clean(app);
        Provider packing=provider(app);Progress stopPacking=new Progress();stopPacking.stopAt=SetupTask.Phase.PACKING_EXPORT;
        cancelled(()->work(activity).run(stopPacking));require(packing.opens==0,"opened before archive completed");clean(app);
        Provider copying=provider(app);Progress stopCopy=new Progress();stopCopy.stopAt=SetupTask.Phase.EXPORTING;
        cancelled(()->work(activity).run(stopCopy));require(copying.last.closes==1,"copy cancellation leaked descriptor");clean(app);
        Provider late=provider(app);DocumentExport lateWork=work(activity);late.opening=lateWork::cancel;
        cancelled(()->lateWork.run(new Progress()));require(late.last.closes==1 && late.signal.isCanceled(),"late descriptor publication survived cancellation");clean(app);
        Provider opening=provider(app);CountDownLatch enteredOpen=new CountDownLatch(1);
        opening.opening=()->{
            enteredOpen.countDown();long end=System.nanoTime()+TimeUnit.SECONDS.toNanos(10);
            while(!opening.signal.isCanceled() && System.nanoTime()<end)Thread.onSpinWait();
            require(opening.signal.isCanceled(),"open was not cancelled");throw new OperationCanceledException();
        };
        BlockingQueue<Runnable> callbacks=new LinkedBlockingQueue<>();SetupTask<DocumentExport.Result> task=new SetupTask<>(callbacks::add);
        task.start(work(activity));require(enteredOpen.await(10,TimeUnit.SECONDS),"never entered provider open");task.cancel();drain(callbacks,task);
        require(task.state().status==SetupTask.Status.CANCELLED && opening.last==null,"blocked open cancellation failed");clean(app);
        Provider blocked=provider(app);CountDownLatch writing=new CountDownLatch(1),closing=new CountDownLatch(1),finishClose=new CountDownLatch(1);
        blocked.output=new OutputStream(){
            public void write(int value)throws IOException {throw new AssertionError("use buffer");}
            public void write(byte[] bytes,int offset,int count)throws IOException {
                writing.countDown();boolean interrupted=false;
                while(closing.getCount()!=0)try{closing.await();}catch(InterruptedException ignored){interrupted=true;}
                if(interrupted)Thread.currentThread().interrupt();throw new IOException("write stopped by descriptor close");
            }
            public void close()throws IOException {
                closing.countDown();try{require(finishClose.await(10,TimeUnit.SECONDS),"close never released");}
                catch(InterruptedException error){Thread.currentThread().interrupt();throw new InterruptedIOException();}
            }
        };
        task.start(work(activity));require(writing.await(10,TimeUnit.SECONDS),"never entered provider write");
        long started=System.nanoTime();task.cancel();require(System.nanoTime()-started<TimeUnit.SECONDS.toNanos(1),"cancel blocked UI");
        require(closing.await(10,TimeUnit.SECONDS),"cancel did not close blocked output");
        require(task.state().status==SetupTask.Status.STOPPING && !task.start(work(activity)),"started over closing output");
        try{StorageSession.INSTANCE.beginSetup();throw new AssertionError("storage released before descriptor closed");}catch(StorageSession.Busy expected){}
        finishClose.countDown();drain(callbacks,task);require(task.state().status==SetupTask.Status.CANCELLED && blocked.last.closes==1,"blocked writer cleanup failed");clean(app);
        Provider retry=provider(app);task.start(work(activity));drain(callbacks,task);
        require(task.state().status==SetupTask.Status.SUCCEEDED && retry.last.closes==1,"retry after provider cancellation failed");clean(app);
        require(Arrays.equals(Files.readAllBytes(save),original),"source save changed during export/recovery");
        Provider empty=provider(app);Files.delete(save);
        failed(PrivateExport.Code.EMPTY,()->work(activity).run(new Progress()));require(empty.opens==0,"empty source touched destination");clean(app);
        Files.write(save,original);
        System.out.println("PASS: exact new-document write; no retained Activity; ZIP completes before provider opens; denied/null/bad descriptors; "+
            "write/flush/close errors; cancelled packing/open/write/late publication; UI stays responsive; closing retains storage lease; retry; source preserved");
    }
}
''',
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    java_home = os.environ.get('JAVA_HOME', '')
    parser.add_argument('--javac', default=shutil.which('javac') or (str(Path(java_home)/'bin/javac') if java_home else None))
    args = parser.parse_args()
    if not args.javac:
        parser.error('a JDK is required')
    (ROOT/'.tmp').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='android-document-export-', dir=ROOT/'.tmp') as temporary:
        scratch = Path(temporary)
        sources = []
        for name, contents in SOURCES.items():
            path = scratch/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents, encoding='utf-8')
            sources.append(str(path))
        classes = scratch/'classes'
        classes.mkdir()
        javac = Path(args.javac).resolve()
        java = javac.with_name('java.exe' if os.name == 'nt' else 'java')
        production = ROOT/'mobile/android/app/src/main/java/com/darkmatter/openq4'
        sources.extend(str(production/name) for name in ('DocumentExport.java', 'PrivateExport.java', 'SetupTask.java', 'StorageSession.java'))
        subprocess.run([str(javac), '--release', '17', '-encoding', 'UTF-8', '-d', str(classes), *sources], check=True)
        subprocess.run([str(java), '-cp', str(classes), 'com.darkmatter.openq4.DocumentExportTest', str(scratch)], check=True)
        verify_archive(scratch/'provider.zip', 'saves')
        print('PASS: provider output independently passes ZIP CRC and manifest hash/length checks')


if __name__ == '__main__':
    main()
