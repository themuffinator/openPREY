#!/usr/bin/env python3
"""Exercise the actual Android retail importer with filesystem and provider failures."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
JAVA = r'''
package com.darkmatter.openq4;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public final class RetailImportTest {
    static Path root, first, second, corrupt;
    static List<RetailData.Expected> catalogue;
    static void require(boolean value,String reason) { if(!value)throw new AssertionError(reason); }
    interface Action { void run() throws Exception; }
    static void failure(RetailImport.Code code,Action action) throws Exception {
        try { action.run();throw new AssertionError("accepted failure: "+code); }
        catch(RetailImport.Failure expected) { require(expected.code==code,"wrong failure: "+expected); }
    }
    static void cancelled(Action action) throws Exception {
        try { action.run();throw new AssertionError("cancellation ignored"); }
        catch(InterruptedIOException expected) {}
    }
    static final class Scenario {
        final File external;
        final Path data, save, config;
        Scenario(String name) throws Exception {
            Path base=Files.createDirectory(root.resolve(name));
            external=base.resolve("external").toFile();
            data=Files.createDirectories(external.toPath().resolve("q4base"));
            save=Files.createDirectories(base.resolve("private/saves/baseoq4/savegames")).resolve("campaign.save");
            Files.writeString(save,"keep this save exactly");
            config=data.resolve("autoexec.cfg");Files.writeString(config,"keep this setting exactly");
        }
        void protect() throws Exception {
            require(Files.readString(save).equals("keep this save exactly"),"private save changed");
            require(Files.readString(config).equals("keep this setting exactly"),"unrelated config changed");
        }
        void core() throws Exception {
            Files.copy(first,data.resolve("pak001.pk4"),StandardCopyOption.REPLACE_EXISTING);
            Files.copy(second,data.resolve("pak002.pk4"),StandardCopyOption.REPLACE_EXISTING);
        }
        Path part(String name) { return external.toPath().resolve(".openq4-import").resolve(name+".part"); }
    }
    static class Source implements RetailImport.Source {
        final List<RetailImport.Entry> items=new ArrayList<>();
        final Map<String,Path> paths=new HashMap<>();
        int opened,closed;
        Source add(String name,Path path) throws Exception { return add(name,path,Files.size(path)); }
        Source add(String name,Path path,long bytes) {
            String id="opaque-provider-id:"+items.size();
            items.add(new RetailImport.Entry(id,name,bytes));paths.put(id,path);return this;
        }
        public List<RetailImport.Entry> entries() { return items; }
        public InputStream open(RetailImport.Entry entry) throws IOException {
            ++opened;
            return new FilterInputStream(Files.newInputStream(paths.get(entry.id))) {
                public void close() throws IOException { super.close();++closed; }
            };
        }
    }
    static Source source() throws Exception { return new Source().add("pak001.pk4",first).add("pak002.pk4",second); }
    static RetailImport.Result run(Source source,Scenario scenario,RetailImport.Storage storage,RetailImport.Progress progress)
            throws IOException {
        return RetailImport.run(source,scenario.external,catalogue,storage,progress);
    }
    static RetailImport.Result run(Source source,Scenario scenario,RetailImport.Progress progress) throws IOException {
        return run(source,scenario,new RetailImport.Storage(),progress);
    }
    static void preserved(Path file,byte[] before) throws IOException {
        require(Arrays.equals(Files.readAllBytes(file),before),"previous destination changed: "+file);
    }
    public static void main(String[] args) throws Exception {
        root=Path.of(args[0]);first=root.resolve("first.pk4");second=root.resolve("second.pk4");corrupt=root.resolve("corrupt.pk4");
        catalogue=List.of(new RetailData.Expected("pak001.pk4",Pk4Checksum.read(first.toFile(),true,null).checksum,true),
            new RetailData.Expected("pak002.pk4",Pk4Checksum.read(second.toFile(),true,null).checksum,true));

        Scenario resume=new Scenario("resume");Source provider=source();
        cancelled(()->run(provider,resume,(phase,name,done,count,bytes,total)->
            !(phase==RetailImport.Phase.COPYING && name.equals("pak002.pk4") && bytes>=65536)));
        require(Files.isRegularFile(resume.data.resolve("pak001.pk4")) && !Files.exists(resume.data.resolve("pak002.pk4")),
            "cancellation lost a committed pack or exposed a partial PK4");
        require(Files.size(resume.part("pak002.pk4"))==65536,"partial copy not bounded at cancellation");
        require(provider.opened==2 && provider.closed==2,"cancelled source stream leaked");
        Files.writeString(resume.part("pak001.pk4"),"abandoned older attempt");
        byte[] committed=Files.readAllBytes(resume.data.resolve("pak001.pk4"));
        Source retry=source();
        long[] last={0};String[] current={""};
        RetailImport.Result result=run(retry,resume,(phase,name,done,count,bytes,total)->{
            String stage=phase+":"+name;
            require(done<=count && bytes>=0 && (total<0 || bytes<=total),"progress outside limits");
            if(stage.equals(current[0]))require(bytes>=last[0],"progress moved backwards within a phase/file");
            current[0]=stage;last[0]=bytes;return true;
        });
        require(result.report.ready() && result.copied==1 && result.reused==1 && retry.opened==1 && retry.closed==1,
            "retry did not retain and revalidate completed files");
        require(!Files.exists(resume.part("pak001.pk4")) && !Files.exists(resume.part("pak002.pk4")),"completed partials retained");
        preserved(resume.data.resolve("pak001.pk4"),committed);resume.protect();

        Scenario verifyCancel=new Scenario("verify-cancel");verifyCancel.core();
        Files.copy(first,verifyCancel.data.resolve("extra.pk4"));
        byte[] previous=Files.readAllBytes(verifyCancel.data.resolve("extra.pk4"));
        Source replacement=source().add("extra.pk4",second);
        cancelled(()->run(replacement,verifyCancel,(phase,name,done,count,bytes,total)->
            !(phase==RetailImport.Phase.VERIFYING && name.equals("extra.pk4") && bytes>0)));
        preserved(verifyCancel.data.resolve("extra.pk4"),previous);verifyCancel.protect();
        require(run(source().add("extra.pk4",second),verifyCancel,null).report.ready(),"verification cancellation could not recover");
        preserved(verifyCancel.data.resolve("extra.pk4"),Files.readAllBytes(second));

        Scenario rename=new Scenario("rename");rename.core();Files.copy(first,rename.data.resolve("extra.pk4"));
        byte[] renameBefore=Files.readAllBytes(rename.data.resolve("extra.pk4"));
        AtomicInteger replacements=new AtomicInteger();
        RetailImport.Storage brokenCommit=new RetailImport.Storage() {
            void replace(File temporary,File target) throws IOException {
                require(Pk4Checksum.read(temporary,true,null).payloadVerified,"promotion before validation");
                replacements.incrementAndGet();throw new IOException("injected rename failure");
            }
        };
        failure(RetailImport.Code.COMMIT_FAILED,()->run(source().add("extra.pk4",second),rename,brokenCommit,null));
        require(replacements.get()==1 && Files.exists(rename.part("extra.pk4")),"failed promotion discarded retry data");
        preserved(rename.data.resolve("extra.pk4"),renameBefore);rename.protect();
        result=run(source().add("extra.pk4",second),rename,null);
        require(result.report.ready() && result.copied==1 && result.reused==2,"failed commit did not recover");

        Scenario invalid=new Scenario("invalid");invalid.core();Files.copy(first,invalid.data.resolve("extra.pk4"));
        byte[] invalidBefore=Files.readAllBytes(invalid.data.resolve("extra.pk4"));
        failure(RetailImport.Code.INVALID_ARCHIVE,()->run(source().add("extra.pk4",corrupt),invalid,null));
        preserved(invalid.data.resolve("extra.pk4"),invalidBefore);invalid.protect();
        Files.writeString(invalid.data.resolve("pak002.pk4"),"previous damaged core");
        failure(RetailImport.Code.WRONG_VERSION,()->run(new Source().add("pak002.pk4",first),invalid,null));
        require(Files.readString(invalid.data.resolve("pak002.pk4")).equals("previous damaged core"),"wrong version replaced destination");
        result=run(source(),invalid,null);
        require(result.report.ready() && result.reused==1 && result.copied==1,"damaged core did not repair");

        Scenario missing=new Scenario("missing");
        result=run(new Source().add("pak001.pk4",first),missing,null);
        require(!result.report.ready() && result.report.issues.stream().anyMatch(i->i.code==RetailData.Code.MISSING_REQUIRED),
            "partial import claimed the full installation is ready");
        missing.protect();

        Scenario space=new Scenario("space");Files.copy(first,space.data.resolve("pak001.pk4"));
        Source lowSource=source();
        RetailImport.Storage noSpace=new RetailImport.Storage(){long available(File path){return 0;}};
        failure(RetailImport.Code.INSUFFICIENT_SPACE,()->run(lowSource,space,noSpace,null));
        require(lowSource.opened==0 && !Files.exists(space.data.resolve("pak002.pk4")),"low-space preflight opened/wrote source");
        space.protect();
        // A stale .part is truncated only after source opening succeeds, and
        // its reclaimed space can be used on retry without erasing the target.
        Files.write(space.part("pak002.pk4"),Files.readAllBytes(second));
        result=run(source(),space,noSpace,null);
        require(result.report.ready() && result.copied==1,"retry failed to account for reclaimed partial space");

        Scenario lost=new Scenario("lost-provider");lost.core();Files.copy(first,lost.data.resolve("extra.pk4"));
        byte[] lostBefore=Files.readAllBytes(lost.data.resolve("extra.pk4"));
        Source disconnected=new Source(){
            public InputStream open(RetailImport.Entry entry) throws IOException {
                return new FilterInputStream(super.open(entry)) {
                    int received;
                    public int read(byte[] bytes,int offset,int count) throws IOException {
                        if(received>=65536)throw new IOException("provider disconnected");
                        int result=super.read(bytes,offset,count);if(result>0)received+=result;return result;
                    }
                };
            }
        };
        disconnected.add("extra.pk4",second);
        failure(RetailImport.Code.COPY_FAILED,()->run(disconnected,lost,null));
        require(disconnected.opened==1 && disconnected.closed==1,"failed provider stream leaked");
        preserved(lost.data.resolve("extra.pk4"),lostBefore);lost.protect();
        failure(RetailImport.Code.SOURCE_CHANGED,()->run(new Source().add("extra.pk4",second,10),lost,null));
        failure(RetailImport.Code.SOURCE_CHANGED,()->run(new Source().add("extra.pk4",second,Files.size(second)+1),lost,null));
        preserved(lost.data.resolve("extra.pk4"),lostBefore);
        result=run(new Source().add("extra.pk4",second,-1),lost,null);
        require(result.report.ready() && result.copied==1,"unknown provider size was not supported");

        Scenario healthy=new Scenario("healthy");healthy.core();
        Source unavailable=new Source(){public InputStream open(RetailImport.Entry entry)throws IOException {
            throw new AssertionError("healthy official file must not be replaced from a provider");
        }};
        unavailable.add("pak001.pk4",corrupt).add("pak002.pk4",corrupt);
        result=run(unavailable,healthy,null);
        require(result.report.ready() && result.copied==0 && result.reused==2,"healthy official data was not preserved");
        healthy.protect();

        File untouched=root.resolve("not-created").toFile();
        failure(RetailImport.Code.DUPLICATE_NAME,()->RetailImport.run(
            new Source().add("pak001.pk4",first).add("PAK001.PK4",first),untouched,null));
        for(String name:List.of("../pak001.pk4","sub/pak001.pk4","C:\\pak001.pk4","a".repeat(129)+".pk4"))
            failure(RetailImport.Code.INVALID_NAME,()->RetailImport.run(new Source().add(name,first),untouched,null));
        for(long bytes:List.of(-2L,(long)Integer.MAX_VALUE+1))
            failure(RetailImport.Code.LIMIT,()->RetailImport.run(new Source().add("pak001.pk4",first,bytes),untouched,null));
        for(int count:List.of(129,4097)) {
            Source excessive=new Source();for(int i=0;i<count;++i)excessive.add("file"+i+".pk4",first);
            failure(RetailImport.Code.LIMIT,()->RetailImport.run(excessive,untouched,null));
        }
        failure(RetailImport.Code.SOURCE_UNAVAILABLE,()->RetailImport.run(new Source().add("game300.pk4",first),untouched,null));
        require(!untouched.exists(),"invalid source created output before preflight");
        Thread.currentThread().interrupt();
        cancelled(()->RetailImport.run(new Source(),untouched,null));
        require(Thread.currentThread().isInterrupted(),"interruption was cleared");Thread.interrupted();
        failure(RetailImport.Code.WRONG_VERSION,()->RetailImport.run(source(),untouched,null));

        Scenario uppercase=new Scenario("uppercase");Files.copy(first,uppercase.data.resolve("PAK001.PK4"));
        result=run(source(),uppercase,null);
        require(result.report.ready() && result.reused==1,"existing uppercase archive not reused");
        try(var entries=Files.list(uppercase.data)) {
            require(entries.filter(p->p.getFileName().toString().equalsIgnoreCase("pak001.pk4")).count()==1,
                "case-alias duplicate was created");
        }

        if(!System.getProperty("os.name").startsWith("Windows")) {
            Scenario linked=new Scenario("linked-target");
            Path link=Files.createSymbolicLink(linked.data.resolve("pak002.pk4"),second);
            try { failure(RetailImport.Code.DESTINATION_UNAVAILABLE,()->run(source(),linked,null)); }
            finally { Files.delete(link); }
            Scenario linkedWork=new Scenario("linked-work");
            link=Files.createSymbolicLink(linkedWork.external.toPath().resolve(".openq4-import"),root);
            try { failure(RetailImport.Code.DESTINATION_UNAVAILABLE,()->run(source(),linkedWork,null)); }
            finally { Files.delete(link); }
            Scenario linkedPart=new Scenario("linked-part");
            Files.createDirectory(linkedPart.external.toPath().resolve(".openq4-import"));
            link=Files.createSymbolicLink(linkedPart.part("pak001.pk4"),first);
            try { failure(RetailImport.Code.DESTINATION_UNAVAILABLE,()->run(source(),linkedPart,null)); }
            finally { Files.delete(link); }
            linked.protect();linkedWork.protect();linkedPart.protect();
        }

        Scenario concurrency=new Scenario("concurrency");
        CountDownLatch firstOpened=new CountDownLatch(1),release=new CountDownLatch(1),started=new CountDownLatch(1);
        AtomicReference<Throwable> error=new AtomicReference<>();AtomicBoolean stopped=new AtomicBoolean();
        Source waiting=new Source(){
            public InputStream open(RetailImport.Entry entry)throws IOException {
                firstOpened.countDown();
                try { if(!release.await(5,TimeUnit.SECONDS))throw new IOException("test release timed out"); }
                catch(InterruptedException interrupted){Thread.currentThread().interrupt();throw new InterruptedIOException();}
                return super.open(entry);
            }
        };
        waiting.add("pak001.pk4",first).add("pak002.pk4",second);
        Source forbidden=new Source(){public InputStream open(RetailImport.Entry entry)throws IOException {
            throw new AssertionError("a second importer entered before the first released ownership");
        }};
        forbidden.add("pak001.pk4",first).add("pak002.pk4",second);
        Thread one=new Thread(()->{try {require(run(waiting,concurrency,null).report.ready(),"first writer failed");}
                                 catch(Throwable failure){error.set(failure);}});
        Thread two=new Thread(()->{started.countDown();try {run(forbidden,concurrency,null);}
                                 catch(InterruptedIOException expected){stopped.set(true);}
                                 catch(Throwable failure){error.set(failure);}});
        one.start();require(firstOpened.await(30,TimeUnit.SECONDS),"first writer did not reach source");
        two.start();require(started.await(5,TimeUnit.SECONDS),"second writer did not start");
        long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(2);
        while(two.isAlive() && two.getState()!=Thread.State.BLOCKED && System.nanoTime()<deadline)Thread.sleep(5);
        boolean blocked=two.getState()==Thread.State.BLOCKED;
        two.interrupt();release.countDown();one.join(30000);two.join(30000);
        require(!one.isAlive() && !two.isAlive() && blocked && stopped.get() && error.get()==null,
            "writer ownership/cancellation failed: "+error.get());concurrency.protect();
        System.out.println("PASS: committed-file retry; copy/verification cancellation; atomic replacement failure; "+
            "CRC/version/size rejection; low space; disconnected/unknown-size providers; exact save/config preservation; "+
            "healthy reuse; names/limits/links; serialized writers and interruption");
    }
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    java_home = os.environ.get('JAVA_HOME', '')
    parser.add_argument('--javac', default=shutil.which('javac') or
                        (str(Path(java_home)/'bin/javac') if java_home else None))
    args = parser.parse_args()
    if not args.javac:
        parser.error('a JDK is required')
    (ROOT/'.tmp').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='android-retail-import-', dir=ROOT/'.tmp') as temporary:
        scratch = Path(temporary)
        for name, value in [('first.pk4', 11), ('second.pk4', 27)]:
            with zipfile.ZipFile(scratch/name, 'w', compression=zipfile.ZIP_STORED) as archive:
                archive.writestr('textures/sample.bin', bytes((i+value) % 256 for i in range(180000)))
        corrupt = bytearray((scratch/'first.pk4').read_bytes())
        name_length, extra_length = struct.unpack_from('<HH', corrupt, 26)
        corrupt[30+name_length+extra_length+2] ^= 255
        (scratch/'corrupt.pk4').write_bytes(corrupt)
        sources = {
            'com/darkmatter/openq4/RetailImportTest.java': JAVA,
            'android/system/ErrnoException.java': '''package android.system;
public class ErrnoException extends Exception { public ErrnoException(Throwable cause){super(cause);} }''',
            'android/system/Os.java': '''package android.system;
import java.nio.file.*;
public final class Os {
    public static void rename(String from,String to)throws ErrnoException {
        try { Files.move(Path.of(from),Path.of(to),StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE); }
        catch(java.io.IOException error){throw new ErrnoException(error);}
    }
}''',
        }
        source_paths = []
        for name, source in sources.items():
            path = scratch/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source)
            source_paths.append(str(path))
        for name in ('Pk4Checksum.java', 'RetailData.java', 'RetailImport.java'):
            source_paths.append(str(ROOT/'mobile/android/app/src/main/java/com/darkmatter/openq4'/name))
        classes = scratch/'classes'
        classes.mkdir()
        javac = Path(args.javac).resolve()
        java = javac.with_name('java.exe' if os.name == 'nt' else 'java')
        subprocess.run([str(javac), '--release', '17', '-d', str(classes), *source_paths], check=True)
        subprocess.run([str(java), '-cp', str(classes), 'com.darkmatter.openq4.RetailImportTest', str(scratch)], check=True)


if __name__ == '__main__':
    main()
