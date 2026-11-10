#!/usr/bin/env python3
"""Compile the real SAF adapter and exercise bounded, read-only provider access."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
'android/net/Uri.java': r'''
package android.net;
public final class Uri {
    public final String scheme,tree,id,kind;
    public Uri(String scheme,String tree,String id,String kind){this.scheme=scheme;this.tree=tree;this.id=id;this.kind=kind;}
    public String getScheme(){return scheme;}
}
''',
'android/provider/DocumentsContract.java': r'''
package android.provider;
import android.net.Uri;
public final class DocumentsContract {
    public static final class Document {
        public static final String COLUMN_DOCUMENT_ID="document_id",COLUMN_DISPLAY_NAME="_display_name",
            COLUMN_MIME_TYPE="mime_type",COLUMN_SIZE="_size",COLUMN_FLAGS="flags",MIME_TYPE_DIR="directory";
        public static final int FLAG_VIRTUAL_DOCUMENT=512;
    }
    public static boolean isTreeUri(Uri uri){return uri.kind.equals("tree");}
    public static String getTreeDocumentId(Uri uri){return uri.tree;}
    public static Uri buildChildDocumentsUriUsingTree(Uri tree,String id){return new Uri("content",tree.tree,id,"children");}
    public static Uri buildDocumentUriUsingTree(Uri tree,String id){return new Uri("content",tree.tree,id,"document");}
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
'android/database/Cursor.java': r'''
package android.database;
public interface Cursor extends AutoCloseable {
    boolean moveToNext(); int getColumnIndex(String name); int getColumnIndexOrThrow(String name);
    String getString(int index); long getLong(int index); int getInt(int index); boolean isNull(int index);
    void close();
}
''',
'android/content/res/AssetFileDescriptor.java': r'''
package android.content.res;
import java.io.*;
public final class AssetFileDescriptor implements Closeable {
    public final InputStream input;
    public boolean failCreate,closed;
    public int created;
    public AssetFileDescriptor(InputStream input){this.input=input;}
    public InputStream createInputStream()throws IOException {
        ++created;if(failCreate)throw new IOException("provider stream failed");return input;
    }
    public void close()throws IOException {if(!closed){closed=true;input.close();}}
}
''',
'android/content/ContentResolver.java': r'''
package android.content;
import android.content.res.AssetFileDescriptor;
import android.database.Cursor;
import android.net.Uri;
import android.os.CancellationSignal;
import java.io.FileNotFoundException;
public abstract class ContentResolver {
    public abstract Cursor query(Uri uri,String[] columns,String selection,String[] args,String sort,CancellationSignal cancel);
    public abstract AssetFileDescriptor openAssetFileDescriptor(Uri uri,String mode,CancellationSignal cancel)throws FileNotFoundException;
}
''',
'android/system/ErrnoException.java': r'''
package android.system;
public class ErrnoException extends Exception {public ErrnoException(Throwable cause){super(cause);}}
''',
'android/system/Os.java': r'''
package android.system;
import java.nio.file.*;
public final class Os {
    public static void rename(String from,String to)throws ErrnoException {
        try{Files.move(Path.of(from),Path.of(to),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}
        catch(java.io.IOException error){throw new ErrnoException(error);}
    }
}
''',
'com/darkmatter/openq4/DocumentSourceTest.java': r'''
package com.darkmatter.openq4;
import android.content.*;
import android.content.res.*;
import android.database.*;
import android.net.*;
import android.os.*;
import android.provider.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.zip.*;

public final class DocumentSourceTest {
    static final String ROOT="selected-tree";
    static final Uri TREE=new Uri("content",ROOT,ROOT,"tree");
    static void require(boolean value,String reason){if(!value)throw new AssertionError(reason);}
    interface Action {void run()throws Exception;}
    static void failed(RetailImport.Code code,Action action)throws Exception {
        try{action.run();throw new AssertionError("accepted "+code);}
        catch(RetailImport.Failure expected){require(expected.code==code,"wrong result: "+expected);}
    }
    static void cancelled(Action action)throws Exception {
        try{action.run();throw new AssertionError("cancellation ignored");}catch(InterruptedIOException expected){}
    }
    static Object[] file(String id,String name,Long bytes){return new Object[]{id,name,"application/zip",bytes,0};}
    static Object[] directory(String id,String name){return new Object[]{id,name,DocumentsContract.Document.MIME_TYPE_DIR,null,0};}
    static final class Rows implements Cursor {
        final List<Object[]> rows;final String[] columns;
        int at=-1;boolean closed,omitOptional;
        Rows(List<Object[]> rows,String[] columns){this.rows=rows;this.columns=columns;}
        public boolean moveToNext(){return ++at<rows.size();}
        public int getColumnIndex(String name){
            for(int i=0;i<columns.length;++i)if(columns[i].equals(name))return omitOptional && i>=3?-1:i;
            return -1;
        }
        public int getColumnIndexOrThrow(String name){int result=getColumnIndex(name);if(result<0)throw new IllegalArgumentException(name);return result;}
        public String getString(int index){return (String)rows.get(at)[index];}
        public long getLong(int index){return ((Number)rows.get(at)[index]).longValue();}
        public int getInt(int index){return ((Number)rows.get(at)[index]).intValue();}
        public boolean isNull(int index){return rows.get(at)[index]==null;}
        public void close(){closed=true;}
    }
    static class Provider extends ContentResolver {
        final Map<String,List<Object[]>> listings=new HashMap<>();
        final Map<String,byte[]> bytes=new HashMap<>();
        final List<String> queried=new ArrayList<>(),opened=new ArrayList<>();
        final List<Rows> cursors=new ArrayList<>();
        AssetFileDescriptor last;
        CancellationSignal lastSignal;
        Runnable beforeQuery,beforeOpen;
        boolean denyQuery,denyOpen,virtualFailure,omitOptional;
        InputStream stream;
        public Cursor query(Uri uri,String[] columns,String selection,String[] args,String sort,CancellationSignal signal) {
            require(uri.scheme.equals("content") && uri.tree.equals(ROOT) && uri.kind.equals("children"),"query escaped selected tree");
            require(selection==null && args==null && sort==null,"unexpected provider filter");
            queried.add(uri.id);lastSignal=signal;
            if(denyQuery)throw new SecurityException("grant revoked");
            if(beforeQuery!=null)beforeQuery.run();
            List<Object[]> content=listings.get(uri.id);if(content==null)return null;
            Rows rows=new Rows(content,columns);rows.omitOptional=omitOptional;cursors.add(rows);return rows;
        }
        public AssetFileDescriptor openAssetFileDescriptor(Uri uri,String mode,CancellationSignal signal)throws FileNotFoundException {
            require(uri.tree.equals(ROOT) && uri.kind.equals("document") && mode.equals("r"),"open escaped tree or requested write access");
            opened.add(uri.id);lastSignal=signal;
            if(denyOpen)throw new SecurityException("grant revoked");
            if(beforeOpen!=null)beforeOpen.run();
            byte[] content=bytes.get(uri.id);
            if(content==null && stream==null)throw new FileNotFoundException(uri.id);
            last=new AssetFileDescriptor(stream!=null?stream:new ByteArrayInputStream(content));
            last.failCreate=virtualFailure;return last;
        }
        void allClosed(){for(Rows cursor:cursors)require(cursor.closed,"provider cursor leaked");}
    }
    static Provider provider(byte[] contents) {
        Provider provider=new Provider();
        provider.listings.put(ROOT,List.of(file("opaque:/one with spaces","PAK001.PK4",(long)contents.length),
            file("ignored","game300.pk4",123L),file("notes","readme.txt",10L),directory("unrelated","textures")));
        provider.bytes.put("opaque:/one with spaces",contents);return provider;
    }
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]);
        ByteArrayOutputStream output=new ByteArrayOutputStream();
        try(ZipOutputStream archive=new ZipOutputStream(output)) {
            archive.putNextEntry(new ZipEntry("sample.bin"));archive.write(new byte[180000]);archive.closeEntry();
        }
        byte[] payload=output.toByteArray();Provider provider=provider(payload);
        try(DocumentSource source=new DocumentSource(provider,TREE)) {
            List<RetailImport.Entry> entries=source.entries();
            require(entries.size()==1 && entries.get(0).name.equals("PAK001.PK4") && entries.get(0).bytes==payload.length,
                "provider metadata/filter mismatch");
            try(InputStream input=source.open(entries.get(0))) {require(Arrays.equals(input.readAllBytes(),payload),"provider stream bytes changed");}
            require(provider.last.closed && provider.last.created==1,"asset descriptor not used/closed");
            failed(RetailImport.Code.SOURCE_UNAVAILABLE,()->source.open(new RetailImport.Entry("outside-tree","pak002.pk4",1)));
            require(provider.opened.size()==1,"unlisted provider id opened");
        }
        provider.allClosed();
        for(Uri uri:Arrays.asList(null,new Uri("file",ROOT,ROOT,"tree"),new Uri("content",ROOT,ROOT,"document")))
            failed(RetailImport.Code.SOURCE_UNAVAILABLE,()->new DocumentSource(provider(payload),uri));

        Provider nested=provider(payload);nested.listings.put(ROOT,List.<Object[]>of(directory("base-id","Q4BASE")));
        nested.listings.put("base-id",List.<Object[]>of(file("nested-file","pak001.pk4",null)));nested.bytes.put("nested-file",payload);
        try(DocumentSource source=new DocumentSource(nested,TREE)) {
            List<RetailImport.Entry> entries=source.entries();require(entries.size()==1 && entries.get(0).bytes==-1,"unknown size not retained");
            require(nested.queried.equals(List.of(ROOT,"base-id")),"installation root did not select immediate q4base");
        }
        nested.allClosed();
        Provider direct=provider(payload);direct.listings.put(ROOT,List.of(
            file("opaque:/one with spaces","pak001.pk4",null),directory("nested","q4base")));
        direct.omitOptional=true;
        try(DocumentSource source=new DocumentSource(direct,TREE)) {
            require(source.entries().get(0).bytes==-1 && direct.queried.equals(List.of(ROOT)),"direct data or absent optional columns mishandled");
        }
        direct.allClosed();
        Provider deep=provider(payload);deep.listings.put(ROOT,List.<Object[]>of(directory("first-level","q4base")));
        deep.listings.put("first-level",List.<Object[]>of(directory("second-level","q4base")));
        try(DocumentSource source=new DocumentSource(deep,TREE)) {
            require(source.entries().isEmpty() && deep.queried.size()==2,"folder search recursed without a bound");
        }

        for(int variant=0;variant<5;++variant) {
            Provider bad=provider(payload);RetailImport.Code expected=RetailImport.Code.SOURCE_UNAVAILABLE;
            switch(variant) {
                case 0: bad.denyQuery=true;break;
                case 1: bad.listings.clear();break;
                case 2: bad.listings.put(ROOT,List.of(file("same","pak001.pk4",1L),file("same","pak002.pk4",1L)));
                        expected=RetailImport.Code.DUPLICATE_NAME;break;
                case 3: bad.listings.put(ROOT,List.of(directory("one","q4base"),directory("two","Q4BASE")));
                        expected=RetailImport.Code.DUPLICATE_NAME;break;
                case 4: Object[] virtual=file("virtual","pak001.pk4",1L);virtual[4]=DocumentsContract.Document.FLAG_VIRTUAL_DOCUMENT;
                        bad.listings.put(ROOT,List.<Object[]>of(virtual));break;
            }
            try(DocumentSource source=new DocumentSource(bad,TREE)) {failed(expected,()->source.entries());}
            bad.allClosed();
        }
        Provider huge=provider(payload);List<Object[]> many=new ArrayList<>();
        for(int i=0;i<5000;++i)many.add(file("id"+i,"readme"+i+".txt",0L));huge.listings.put(ROOT,many);
        try(DocumentSource source=new DocumentSource(huge,TREE)) {failed(RetailImport.Code.LIMIT,()->source.entries());}
        require(huge.cursors.get(0).at==4096,"provider enumeration exceeded bound");huge.allClosed();

        Provider revoked=provider(payload);
        try(DocumentSource source=new DocumentSource(revoked,TREE)) {
            RetailImport.Entry entry=source.entries().get(0);revoked.denyOpen=true;
            failed(RetailImport.Code.SOURCE_UNAVAILABLE,()->source.open(entry));
        }
        Provider failedStream=provider(payload);failedStream.virtualFailure=true;
        try(DocumentSource source=new DocumentSource(failedStream,TREE)) {
            RetailImport.Entry entry=source.entries().get(0);
            failed(RetailImport.Code.SOURCE_UNAVAILABLE,()->source.open(entry));
            require(failedStream.last.closed,"descriptor leaked when stream creation failed");
        }
        Provider interruptedQuery=provider(payload);
        try(DocumentSource source=new DocumentSource(interruptedQuery,TREE)) {
            interruptedQuery.beforeQuery=source::close;cancelled(()->source.entries());
        }
        interruptedQuery.allClosed();
        Provider interruptedOpen=provider(payload);
        try(DocumentSource source=new DocumentSource(interruptedOpen,TREE)) {
            RetailImport.Entry entry=source.entries().get(0);interruptedOpen.beforeOpen=source::close;
            cancelled(()->source.open(entry));require(interruptedOpen.last.closed,"cancelled open leaked descriptor");
        }
        Provider unused=provider(payload);DocumentSource alreadyClosed=new DocumentSource(unused,TREE);alreadyClosed.close();
        cancelled(()->alreadyClosed.entries());require(unused.queried.isEmpty(),"closed provider still queried");

        Provider blocked=provider(payload);CountDownLatch reading=new CountDownLatch(1),closed=new CountDownLatch(1);
        blocked.stream=new InputStream() {
            public int read()throws IOException {return read(new byte[1],0,1);}
            public int read(byte[] buffer,int offset,int count)throws IOException {
                reading.countDown();
                try {if(!closed.await(5,TimeUnit.SECONDS))throw new IOException("test close timeout");}
                catch(InterruptedException interrupted){Thread.currentThread().interrupt();throw new InterruptedIOException();}
                throw new IOException("descriptor closed during provider read");
            }
            public void close(){closed.countDown();}
        };
        try(DocumentSource source=new DocumentSource(blocked,TREE)) {
            InputStream input=source.open(source.entries().get(0));AtomicReference<Throwable> error=new AtomicReference<>();
            AtomicBoolean cancelled=new AtomicBoolean();
            Thread reader=new Thread(()->{try{input.read(new byte[100]);}
                catch(InterruptedIOException expected){cancelled.set(true);}catch(Throwable failure){error.set(failure);}});
            reader.start();require(reading.await(5,TimeUnit.SECONDS),"reader did not start");source.close();reader.join(5000);
            require(!reader.isAlive() && cancelled.get() && error.get()==null && blocked.last.closed,
                "cancellation did not close the active descriptor/read");input.close();
        }

        // The real adapter and real importer work together without assuming
        // local filesystem paths or seekable provider streams.
        Provider complete=provider(payload);complete.listings.put(ROOT,List.of(
            file("one","pak001.pk4",(long)payload.length),file("two","pak002.pk4",null)));
        complete.bytes.put("one",payload);complete.bytes.put("two",payload);
        Path reference=root.resolve("reference.pk4");Files.write(reference,payload);
        int checksum=Pk4Checksum.read(reference.toFile(),true,null).checksum;
        try(DocumentSource source=new DocumentSource(complete,TREE)) {
            RetailImport.Result result=RetailImport.run(source,root.resolve("external").toFile(),List.of(
                new RetailData.Expected("pak001.pk4",checksum,true),new RetailData.Expected("pak002.pk4",checksum,true)),
                new RetailImport.Storage(),null);
            require(result.report.ready() && result.copied==2,"document-to-installation integration failed");
        }
        complete.allClosed();
        require(Arrays.equals(Files.readAllBytes(root.resolve("external/q4base/pak002.pk4")),payload),"imported provider bytes differ");
        System.out.println("PASS: selected-tree/read-only URI use; bounded flat/q4base enumeration; opaque IDs; "+
            "unknown metadata; revoked/null/virtual providers; cursor/descriptor cleanup; cancellation during query/open/read; "+
            "and real document-source/importer integration");
    }
}
''',
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    java_home = os.environ.get('JAVA_HOME', '')
    parser.add_argument('--javac', default=shutil.which('javac') or
                        (str(Path(java_home)/'bin/javac') if java_home else None))
    args = parser.parse_args()
    if not args.javac:
        parser.error('a JDK is required')
    (ROOT/'.tmp').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='android-document-', dir=ROOT/'.tmp') as temporary:
        scratch = Path(temporary)
        paths = []
        for name, text in SOURCES.items():
            path = scratch/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            paths.append(str(path))
        for name in ('Pk4Checksum.java', 'RetailData.java', 'RetailImport.java', 'DocumentSource.java'):
            paths.append(str(ROOT/'mobile/android/app/src/main/java/com/darkmatter/openq4'/name))
        classes = scratch/'classes'
        classes.mkdir()
        javac = Path(args.javac).resolve()
        java = javac.with_name('java.exe' if os.name == 'nt' else 'java')
        subprocess.run([str(javac), '--release', '17', '-d', str(classes), *paths], check=True)
        subprocess.run([str(java), '-cp', str(classes), 'com.darkmatter.openq4.DocumentSourceTest', str(scratch)], check=True)


if __name__ == '__main__':
    main()
