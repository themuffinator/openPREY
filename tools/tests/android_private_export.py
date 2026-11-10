#!/usr/bin/env python3
"""Exercise read-only save/log ZIP snapshots and their native storage lease."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
JAVA = r'''
package com.darkmatter.openq4;
import java.io.*;
import java.nio.file.*;
import java.nio.file.attribute.FileTime;
import java.util.*;
import java.util.concurrent.atomic.*;
import java.util.zip.*;

public final class PrivateExportTest {
    static void require(boolean value,String reason){if(!value)throw new AssertionError(reason);}
    interface Action {void run()throws Exception;}
    static void failure(PrivateExport.Code code,Action action)throws Exception {
        try{action.run();throw new AssertionError("accepted "+code);}
        catch(PrivateExport.Failure expected){require(expected.code==code,"wrong result "+expected);}
    }
    static void cancelled(Action action)throws Exception {
        try{action.run();throw new AssertionError("ignored cancellation");}catch(InterruptedIOException expected){}
    }
    static void available()throws Exception {Object owner=StorageSession.INSTANCE.beginSetup();StorageSession.INSTANCE.endSetup(owner);}
    static void write(Path path,byte[] bytes)throws Exception {Files.createDirectories(path.getParent());Files.write(path,bytes);}
    static void noTemporary(Path cache)throws Exception {
        Path work=cache.resolve("openq4-exports");
        if(Files.exists(work))try(var files=Files.list(work)) {
            require(files.noneMatch(file->file.getFileName().toString().startsWith("export-")),"abandoned private snapshot");
        }
    }
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]),files=root.resolve("private"),cache=root.resolve("cache");
        byte[] save=new byte[180000];new Random(42).nextBytes(save);
        Path source=files.resolve("saves/baseoq4/savegames/Campaign.save");write(source,save);
        write(files.resolve("saves/baseoq4/savegames/Campaign.txt"),"Saved mission".getBytes());
        write(files.resolve("saves/baseoq4/savegames/Campaign.tga"),new byte[]{1,2,3});
        write(files.resolve("saves/q4xbase/savegames/été.save"),"Awakening save".getBytes(java.nio.charset.StandardCharsets.UTF_8));
        write(files.resolve("saves/baseoq4/logs/openq4.log"),"diagnostic log\n".getBytes());
        write(files.resolve("saves/baseoq4/logs/fatal.txt"),"fatal details\n".getBytes());
        write(files.resolve("saves/baseoq4/openq4.cfg"),"private settings not selected".getBytes());
        write(files.resolve("packages/keep.pk4"),"not game saves".getBytes());
        Path keep=cache.resolve("openq4-exports/keep.txt");write(keep,"unrelated cache".getBytes());
        Path abandoned=cache.resolve("openq4-exports/export-abandoned.zip.part");write(abandoned,new byte[100]);
        List<Long> progress=new ArrayList<>();
        PrivateExport.Snapshot snapshot=PrivateExport.create(files.toFile(),cache.toFile(),PrivateExport.Kind.SAVES,
            (name,done,count,bytes,total)->{require(bytes<=total && done<=count,"invalid progress");progress.add(bytes);return true;});
        require(snapshot.count==4 && snapshot.sourceBytes==save.length+13+3+14 && snapshot.bytes>0,"snapshot metadata");
        require(!Files.exists(abandoned) && Files.readString(keep).equals("unrelated cache"),"stale cleanup scope");
        try{PrivateExport.create(files.toFile(),cache.toFile(),PrivateExport.Kind.LOGS,null);throw new AssertionError("second export removed live snapshot");}
        catch(StorageSession.Busy expected){}
        try{StorageSession.INSTANCE.beginSetup();throw new AssertionError("import overlapped a live export");}catch(StorageSession.Busy expected){}
        Files.copy(snapshot.file.toPath(),root.resolve("saves.zip"));
        try(ZipFile archive=new ZipFile(snapshot.file)) {
            require(archive.size()==5 && archive.getEntry("baseoq4/openq4.cfg")==null && archive.getEntry("baseoq4/logs/openq4.log")==null,
                "save export included unrelated data");
            require(Arrays.equals(archive.getInputStream(archive.getEntry("baseoq4/savegames/Campaign.save")).readAllBytes(),save),"save bytes changed");
        }
        snapshot.close();snapshot.close();available();noTemporary(cache);
        try(PrivateExport.Snapshot logs=PrivateExport.create(files.toFile(),cache.toFile(),PrivateExport.Kind.LOGS,null)) {
            require(logs.count==2,"log selection");Files.copy(logs.file.toPath(),root.resolve("logs.zip"));
        }
        available();noTemporary(cache);
        Object diagnosticsOwner=StorageSession.INSTANCE.beginSetup();
        Path diagnostic=files.resolve("saves/baseoq4/logs/setup.log");
        try {
            IOException firstCause=new IOException("provider failure\n"+"é".repeat(8192));
            IOException secondCause=new IOException("nested cause",firstCause);firstCause.initCause(secondCause);
            require(SetupDiagnostics.record(files.toFile(),"Import failed\nforged line",firstCause),"diagnostic write failed");
            String recorded=Files.readString(diagnostic);
            require(recorded.contains("Import failed forged line") && recorded.contains("java.io.IOException") && recorded.contains("nested cause") &&
                recorded.length()<8192 && recorded.split("provider failure",-1).length==3,"diagnostic message/cause bounds");
            byte[] old=new byte[256*1024];Arrays.fill(old,(byte)'x');Files.write(diagnostic,old);
            require(SetupDiagnostics.record(files.toFile(),"Next attempt",null),"diagnostic rotation failed");
            require(Files.size(diagnostic)<1024 && Arrays.equals(Files.readAllBytes(diagnostic.resolveSibling("setup-previous.log")),old),"bounded log rotation lost previous log");
        } finally {StorageSession.INSTANCE.endSetup(diagnosticsOwner);}
        try(PrivateExport.Snapshot logs=PrivateExport.create(files.toFile(),cache.toFile(),PrivateExport.Kind.LOGS,null)) {
            require(logs.count==4,"setup diagnostics missing from log export");Files.copy(logs.file.toPath(),root.resolve("diagnostics.zip"));
        }
        available();noTemporary(cache);
        for(boolean late:new boolean[]{false,true}) {
            AtomicInteger boundaries=new AtomicInteger();
            cancelled(()->PrivateExport.create(files.toFile(),cache.toFile(),PrivateExport.Kind.SAVES,
                (name,done,count,bytes,total)-> late ? !(name.isEmpty() && count>0 && done==count && boundaries.incrementAndGet()==2) : bytes<65536));
            available();noTemporary(cache);
        }
        Thread.currentThread().interrupt();
        cancelled(()->PrivateExport.create(files.toFile(),cache.toFile(),PrivateExport.Kind.SAVES,null));
        require(Thread.currentThread().isInterrupted(),"export cleared interruption");Thread.interrupted();available();
        PrivateExport.Storage full=new PrivateExport.Storage(){@Override long available(File directory){return 0;}};
        try{PrivateExport.create(files.toFile(),cache.toFile(),PrivateExport.Kind.SAVES,full,null);throw new AssertionError("ignored low space");}
        catch(PrivateExport.Failure expected){require(expected.code==PrivateExport.Code.INSUFFICIENT_SPACE && expected.requiredBytes>save.length && expected.availableBytes==0,"space fields");}
        available();noTemporary(cache);
        failure(PrivateExport.Code.EMPTY,()->PrivateExport.create(root.resolve("empty").toFile(),cache.toFile(),PrivateExport.Kind.SAVES,null));available();
        AtomicBoolean changed=new AtomicBoolean();
        failure(PrivateExport.Code.CHANGED_FILE,()->PrivateExport.create(files.toFile(),cache.toFile(),PrivateExport.Kind.SAVES,
            (name,done,count,bytes,total)->{
                if(done==count && count>0 && changed.compareAndSet(false,true)) {
                    try{Files.setLastModifiedTime(source,FileTime.fromMillis(Files.getLastModifiedTime(source).toMillis()+4000));}
                    catch(Exception error){throw new RuntimeException(error);}
                }
                return true;
            }));available();noTemporary(cache);
        AtomicBoolean added=new AtomicBoolean();Path extra=source.resolveSibling("new.save");
        failure(PrivateExport.Code.CHANGED_FILE,()->PrivateExport.create(files.toFile(),cache.toFile(),PrivateExport.Kind.SAVES,
            (name,done,count,bytes,total)->{
                if(done==count && count>0 && added.compareAndSet(false,true)) {
                    try{Files.writeString(extra,"new");}catch(Exception error){throw new RuntimeException(error);}
                }return true;
            }));Files.delete(extra);available();noTemporary(cache);
        Path deep=files.resolve("saves/deep/savegames");for(int i=0;i<18;++i)deep=deep.resolve("d");
        write(deep.resolve("depth.save"),new byte[1]);
        failure(PrivateExport.Code.LIMIT,()->PrivateExport.create(files.toFile(),cache.toFile(),PrivateExport.Kind.SAVES,null));
        Files.delete(deep.resolve("depth.save"));for(int i=0;i<18;++i){Files.delete(deep);deep=deep.getParent();}Files.delete(deep);Files.delete(deep.getParent());available();
        Path obstruction=cache.resolve("openq4-exports/export-directory.zip.part");write(obstruction.resolve("keep.txt"),new byte[]{7});
        failure(PrivateExport.Code.CACHE_UNAVAILABLE,()->PrivateExport.create(files.toFile(),cache.toFile(),PrivateExport.Kind.SAVES,null));
        require(Files.readAllBytes(obstruction.resolve("keep.txt"))[0]==7,"cleanup recursively deleted an unexpected directory");
        Files.delete(obstruction.resolve("keep.txt"));Files.delete(obstruction);available();
        if(!System.getProperty("os.name").startsWith("Windows")) {
            Path alias=source.resolveSibling("campaign.save");
            if(!Files.exists(alias)) {
                Files.writeString(alias,"alias");
                failure(PrivateExport.Code.UNSAFE_PATH,()->PrivateExport.create(files.toFile(),cache.toFile(),PrivateExport.Kind.SAVES,null));Files.delete(alias);available();
            } else System.out.println("SKIP: case aliases require a case-sensitive filesystem (this WSL mount is not)");
            Path link=source.resolveSibling("linked.save");Files.createSymbolicLink(link,root.resolve("saves.zip"));
            failure(PrivateExport.Code.UNSAFE_PATH,()->PrivateExport.create(files.toFile(),cache.toFile(),PrivateExport.Kind.SAVES,null));Files.delete(link);available();
            Path reserved=source.resolveSibling("CON.save");Files.writeString(reserved,"reserved");
            failure(PrivateExport.Code.UNSAFE_PATH,()->PrivateExport.create(files.toFile(),cache.toFile(),PrivateExport.Kind.SAVES,null));Files.delete(reserved);available();
            Path staleLink=cache.resolve("openq4-exports/export-link.zip.part");Files.createSymbolicLink(staleLink,source);
            failure(PrivateExport.Code.UNSAFE_PATH,()->PrivateExport.create(files.toFile(),cache.toFile(),PrivateExport.Kind.SAVES,null));Files.delete(staleLink);available();
            Path linkedFiles=root.resolve("linked-diagnostics");Files.createDirectories(linkedFiles.resolve("saves/baseoq4"));
            Files.createSymbolicLink(linkedFiles.resolve("saves/baseoq4/logs"),diagnostic.getParent());
            byte[] previousLog=Files.readAllBytes(diagnostic);
            Object owner=StorageSession.INSTANCE.beginSetup();
            try{require(!SetupDiagnostics.record(linkedFiles.toFile(),"must not escape",null),"diagnostics followed link");}
            finally{StorageSession.INSTANCE.endSetup(owner);}
            require(Arrays.equals(Files.readAllBytes(diagnostic),previousLog),"linked diagnostic target changed");
        } else System.out.println("SKIP: Linux fixture covers Android-style link/case/reserved-name behavior");
        Object game=new Object();StorageSession.INSTANCE.activityCreated(game);
        try{PrivateExport.create(files.toFile(),cache.toFile(),PrivateExport.Kind.SAVES,null);throw new AssertionError("export overlapped game");}
        catch(StorageSession.Busy expected){}finally{StorageSession.INSTANCE.activityDestroyed(game);}
        available();noTemporary(cache);require(Arrays.equals(Files.readAllBytes(source),save),"export changed original save bytes");
        System.out.println("PASS: save/log selection; byte-preserving ZIPs and manifest; live snapshot owns storage; cancellation before/after sync; "+
            "failure cleanup/retry; low space; changed file/folder rejection; path/depth/alias/link bounds; scoped stale cleanup; "+
            "bounded diagnostic messages/causes/rotation and export; originals preserved");
    }
}
'''


def verify_archive(path: Path, kind: str) -> None:
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        manifest = archive.read('openq4-export.tsv').decode('utf-8').splitlines()
        assert manifest[0] == f'openQ4-export-v1\t{kind}'
        indexed = set()
        for row in manifest[1:]:
            digest, size, name = row.split('\t')
            contents = archive.read(name)
            assert hashlib.sha256(contents).hexdigest() == digest and len(contents) == int(size)
            indexed.add(name)
        assert indexed | {'openq4-export.tsv'} == set(archive.namelist())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    java_home = os.environ.get('JAVA_HOME', '')
    parser.add_argument('--javac', default=shutil.which('javac') or (str(Path(java_home)/'bin/javac') if java_home else None))
    args = parser.parse_args()
    if not args.javac:
        parser.error('a JDK is required')
    (ROOT/'.tmp').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='android-private-export-', dir=ROOT/'.tmp') as temporary:
        scratch = Path(temporary)
        source = scratch/'PrivateExportTest.java'
        source.write_text(JAVA, encoding='utf-8')
        classes = scratch/'classes'
        classes.mkdir()
        javac = Path(args.javac).resolve()
        java = javac.with_name('java.exe' if os.name == 'nt' else 'java')
        production = ROOT/'mobile/android/app/src/main/java/com/darkmatter/openq4'
        subprocess.run([str(javac), '--release', '17', '-encoding', 'UTF-8', '-d', str(classes), str(source),
                        str(production/'PrivateExport.java'), str(production/'StorageSession.java'), str(production/'SetupDiagnostics.java')], check=True)
        subprocess.run([str(java), '-cp', str(classes), 'com.darkmatter.openq4.PrivateExportTest', str(scratch)], check=True)
        verify_archive(scratch/'saves.zip', 'saves')
        verify_archive(scratch/'logs.zip', 'logs')
        verify_archive(scratch/'diagnostics.zip', 'logs')
        print('PASS: independent Python ZIP CRC, exact entry inventory and every manifest SHA-256/length')


if __name__ == '__main__':
    main()
