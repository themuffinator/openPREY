#!/usr/bin/env python3
"""Check the actual Java retail verifier against native MD4 and damaged ZIPs."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
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

public final class RetailDataTest {
    static void require(boolean value,String reason) { if(!value)throw new AssertionError(reason); }
    static boolean issue(RetailData.Report report,RetailData.Code code,String name,boolean blocking) {
        return report.issues.stream().anyMatch(i->i.code==code && i.name.equals(name) && i.blocking==blocking);
    }
    static void scanner(Path root,String retail) throws Exception {
        List<String> expected=Files.readAllLines(root.resolve("official.tsv"));
        List<String> actual=new ArrayList<>();
        for(RetailData.Expected item:RetailData.OFFICIAL)
            actual.add(item.name+"\t"+String.format("%08x",item.checksum)+"\t"+item.required);
        require(actual.equals(expected),"Java required/optional baseline diverged from native engine");
        require(RetailData.LANGUAGES.equals(Files.readAllLines(root.resolve("languages.txt"))),"language names diverged from engine");
        for(String name:List.of("game000.pk4","game100.pk4","game200.pk4","game300.pk4","GaMeX86.PK4"))
            require(RetailData.ignoredGameCode(name),"retail game code was admitted: "+name);
        for(String name:List.of("game400.pk4","gameplay.pk4","game000.pk4.bak"))
            require(!RetailData.ignoredGameCode(name),"other media falsely ignored: "+name);
        File stored=root.resolve("stored.pk4").toFile();
        int checksum=Pk4Checksum.read(stored,true,null).checksum;
        List<RetailData.Expected> catalogue=List.of(
            new RetailData.Expected("pak001.pk4",checksum,true),
            new RetailData.Expected("pak002.pk4",checksum,true),
            new RetailData.Expected("pak023.pk4",checksum,false),
            new RetailData.Expected("zpak_english.pk4",checksum,false));
        Path data=Files.createDirectory(root.resolve("q4base"));
        File directory=data.toFile();
        RetailData.Report report=RetailData.scan(directory,catalogue,null);
        require(!report.ready() && issue(report,RetailData.Code.MISSING_REQUIRED,"pak001.pk4",true) &&
            issue(report,RetailData.Code.MISSING_REQUIRED,"pak002.pk4",true),"empty folder accepted");
        Files.copy(stored.toPath(),data.resolve("PAK001.PK4"));
        report=RetailData.scan(directory,catalogue,null);
        require(!report.ready() && !issue(report,RetailData.Code.MISSING_REQUIRED,"pak001.pk4",true),
            "partial folder accepted or uppercase name missed");
        Files.copy(stored.toPath(),data.resolve("pak002.pk4"));
        Files.writeString(data.resolve("game300.pk4"),"ignored native game code");
        long[] state={0,-1};int[] calls={0};
        report=RetailData.scan(directory,catalogue,(phase,name,done,count,bytes,total)->{
            require(done<=count,"archive count exceeds plan");
            if(phase==RetailData.Phase.VERIFYING) {
                require(bytes>=state[0] && bytes<=total,"scan progress is not bounded/monotonic");
                require(state[1]<0 || state[1]==total,"scan total changed");
                state[0]=bytes;state[1]=total;++calls[0];
            }
            return true;
        });
        require(report.ready() && report.verified.size()==2 && calls[0]>4 && state[0]==state[1] &&
            issue(report,RetailData.Code.MISSING_OPTIONAL,"pak023.pk4",false) &&
            issue(report,RetailData.Code.MISSING_LANGUAGE,"",false),"optional/language absence incorrectly blocks core data");
        Files.copy(stored.toPath(),data.resolve("zpak_english_01.pk4"));
        require(issue(RetailData.scan(directory,catalogue,null),RetailData.Code.MISSING_LANGUAGE,"",false),
            "language patch mistaken for dialogue base");
        Files.copy(stored.toPath(),data.resolve("ZPAK_FRENCH.PK4"));
        report=RetailData.scan(directory,catalogue,null);
        require(report.ready() && !issue(report,RetailData.Code.MISSING_LANGUAGE,"",false) &&
            issue(report,RetailData.Code.UNRECOGNIZED_ARCHIVE,"ZPAK_FRENCH.PK4",false),
            "valid alternate locale rejected or falsely claimed known checksum");
        Files.copy(root.resolve("reversed.pk4"),data.resolve("pak023.pk4"));
        report=RetailData.scan(directory,catalogue,null);
        require(report.ready() && issue(report,RetailData.Code.CHECKSUM_MISMATCH,"pak023.pk4",false),
            "optional checksum disagreement changed required engine baseline");
        Files.copy(root.resolve("reversed.pk4"),data.resolve("pak002.pk4"),StandardCopyOption.REPLACE_EXISTING);
        report=RetailData.scan(directory,catalogue,null);
        require(!report.ready() && issue(report,RetailData.Code.CHECKSUM_MISMATCH,"pak002.pk4",true),
            "required checksum mismatch accepted");
        Files.copy(stored.toPath(),data.resolve("pak002.pk4"),StandardCopyOption.REPLACE_EXISTING);
        Files.copy(root.resolve("corrupt.pk4"),data.resolve("pak023.pk4"),StandardCopyOption.REPLACE_EXISTING);
        report=RetailData.scan(directory,catalogue,null);
        require(!report.ready() && issue(report,RetailData.Code.CORRUPT_ENTRY,"pak023.pk4",true),
            "damaged optional archive reported as ready to mount");
        Files.delete(data.resolve("pak023.pk4"));
        File duplicate=new File(data.toString()) {
            public File getCanonicalFile() { return this; }
            public File[] listFiles() { return new File[]{new File(this,"pak001.pk4"),new File(this,"PAK001.PK4")}; }
        };
        report=RetailData.scan(duplicate,catalogue,null);
        require(!report.ready() && issue(report,RetailData.Code.DUPLICATE_ARCHIVE,"pak001.pk4",true),
            "case-alias duplicates accepted");
        for(int entries:List.of(129,4097)) {
            File excessive=new File(data.toString()) {
                public File getCanonicalFile() { return this; }
                public File[] listFiles() {
                    File[] result=new File[entries];
                    for(int i=0;i<entries;++i)result[i]=new File(this,"extra-"+i+".pk4");
                    return result;
                }
            };
            report=RetailData.scan(excessive,catalogue,null);
            require(!report.ready() && issue(report,RetailData.Code.LIMIT,"q4base",true),"unbounded folder inventory");
        }
        if(!System.getProperty("os.name").startsWith("Windows")) {
            Path link=Files.createSymbolicLink(data.resolve("pak023.pk4"),stored.toPath());
            report=RetailData.scan(directory,catalogue,null);
            require(!report.ready() && issue(report,RetailData.Code.INVALID_ARCHIVE,"pak023.pk4",true),
                "retail destination followed unexpected link");
            Files.delete(link);
        }
        Path notFile=Files.createDirectory(data.resolve("pak023.pk4"));
        require(!RetailData.scan(directory,catalogue,null).ready(),"directory accepted as PK4");
        Files.delete(notFile);
        require(!RetailData.scan(root.resolve("unavailable").toFile(),catalogue,null).ready(),"unavailable folder accepted");
        boolean cancelled=false;
        try { RetailData.scan(directory,catalogue,(phase,name,done,count,bytes,total)->
                phase!=RetailData.Phase.VERIFYING || bytes<65536); }
        catch(InterruptedIOException expectedCancel) { cancelled=true; }
        require(cancelled && RetailData.scan(directory,catalogue,null).ready(),"scan cancellation/retry failed");
        boolean[] changed={false};
        report=RetailData.scan(directory,catalogue,(phase,name,done,count,bytes,total)->{
            if(phase==RetailData.Phase.VERIFYING && done>0 && !changed[0]) {
                try { Files.write(data.resolve("PAK001.PK4"),new byte[]{0},StandardOpenOption.APPEND); }
                catch(IOException error) { throw new UncheckedIOException(error); }
                changed[0]=true;
            }
            return true;
        });
        require(changed[0] && !report.ready() && issue(report,RetailData.Code.CHANGED_FILE,"PAK001.PK4",true),
            "earlier file changed during later verification was accepted");
        Files.copy(stored.toPath(),data.resolve("PAK001.PK4"),StandardCopyOption.REPLACE_EXISTING);
        changed[0]=false;
        report=RetailData.scan(directory,catalogue,(phase,name,done,count,bytes,total)->{
            if(phase==RetailData.Phase.VERIFYING && bytes>0 && !changed[0]) {
                try { Files.copy(stored.toPath(),data.resolve("new.pk4")); }
                catch(IOException error) { throw new UncheckedIOException(error); }
                changed[0]=true;
            }
            return true;
        });
        require(changed[0] && !report.ready() && issue(report,RetailData.Code.CHANGED_FILE,"q4base",true),
            "directory changed during verification was accepted");
        // The normal entry point must use the real required catalogue.
        report=RetailData.scan(directory,null);
        require(!report.ready() && issue(report,RetailData.Code.MISSING_REQUIRED,"pak022.pk4",true) &&
            issue(report,RetailData.Code.CHECKSUM_MISMATCH,"PAK001.PK4",true),"production scan bypassed baseline");
        if(!retail.isEmpty()) {
            report=RetailData.scan(new File(retail),null);
            require(report.ready(),"actual media failed complete required-set scan");
            require(report.issues.isEmpty(),"actual media unexpectedly warned: "+report.issues.size());
            System.out.println("verified complete retail set: "+report.verified.size()+" archives");
        }
        System.out.println("PASS: native catalogue/language parity; required, optional, alternate-language and ignored-code selection; "+
            "case aliases, damaged optional media, missing files, whole-set changes, progress and cancellation/retry");
    }
    static void invalid(File file,Pk4Checksum.Problem expected,boolean full) throws Exception {
        try { Pk4Checksum.read(file,full,null);throw new AssertionError("accepted invalid archive: "+file); }
        catch(Pk4Checksum.Invalid error) { require(expected==null || error.problem==expected,"wrong failure: "+error); }
        catch(IOException error) { require(expected==null,"expected structured failure: "+error); }
    }
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);int vectors=0,archives=0;
        for(String line:Files.readAllLines(root.resolve("vectors.tsv"))) {
            String[] fields=line.split("\t");
            int expected=(int)Long.parseLong(fields[1],16);
            require(Pk4Checksum.blockChecksum(Files.readAllBytes(root.resolve(fields[0])))==expected,"native/Java MD4 mismatch: "+fields[0]);
            ++vectors;
        }
        for(String line:Files.readAllLines(root.resolve("archives.tsv"))) {
            String[] fields=line.split("\t");File archive=new File(fields[0]);
            int expected=(int)Long.parseLong(fields[1],16);long expanded=Long.parseLong(fields[2]);
            Pk4Checksum.Result metadata=Pk4Checksum.read(archive,false,null);
            require(metadata.checksum==expected && metadata.expandedBytes==expanded && !metadata.payloadVerified,"metadata verification mismatch: "+archive.getName());
            long[] progress={0,-1};
            Pk4Checksum.Result full=Pk4Checksum.read(archive,true,(done,total)->{
                require(done>=progress[0] && done<=total,"nonmonotonic/out-of-range progress");
                if(total>0) {
                    require(progress[1]<0 || progress[1]==total,"verification total changed");progress[1]=total;
                }
                progress[0]=done;return true;
            });
            require(full.checksum==expected && full.expandedBytes==expanded && full.payloadVerified && progress[0]==expanded,
                "payload verification mismatch: "+archive.getName());
            System.out.println("verified "+archive.getName()+" checksum="+Long.toHexString(full.checksum&0xffffffffL)+" bytes="+expanded);
            ++archives;
        }
        invalid(root.resolve("invalid.pk4").toFile(),null,true);
        invalid(root.resolve("truncated.pk4").toFile(),null,true);
        invalid(root.resolve("duplicate.pk4").toFile(),Pk4Checksum.Problem.INVALID_ARCHIVE,true);
        invalid(root.resolve("large-entry.pk4").toFile(),Pk4Checksum.Problem.LIMIT,false);
        invalid(root.resolve("expanded-limit.pk4").toFile(),Pk4Checksum.Problem.LIMIT,false);
        invalid(root.resolve("many-entries.pk4").toFile(),Pk4Checksum.Problem.LIMIT,false);
        invalid(root.resolve("large-directory.pk4").toFile(),Pk4Checksum.Problem.LIMIT,false);
        invalid(root.resolve("multi-disk.pk4").toFile(),Pk4Checksum.Problem.INVALID_ARCHIVE,false);
        File corrupt=root.resolve("corrupt.pk4").toFile();
        require(!Pk4Checksum.read(corrupt,false,null).payloadVerified,"metadata falsely claimed payload verification");
        invalid(corrupt,Pk4Checksum.Problem.CORRUPT_ENTRY,true);
        File oversized=new File(root.resolve("stored.pk4").toString()) {
            public File getCanonicalFile() { return this; }
            public long length() { return (long)Integer.MAX_VALUE+1; }
        };
        invalid(oversized,Pk4Checksum.Problem.LIMIT,false);
        File stored=root.resolve("stored.pk4").toFile();boolean cancelled=false;
        try { Pk4Checksum.read(stored,true,(done,total)->done<65536); }
        catch(InterruptedIOException expected) { cancelled=true; }
        require(cancelled,"progress cancellation did not stop payload reading");
        Thread.currentThread().interrupt();cancelled=false;
        try { Pk4Checksum.read(stored,true,null); }
        catch(InterruptedIOException expected) { cancelled=true; }
        require(cancelled && Thread.currentThread().isInterrupted(),"thread cancellation was swallowed");
        Thread.interrupted();
        require(Pk4Checksum.read(stored,true,null).payloadVerified,"cancelled verifier could not be retried");
        Path changing=root.resolve("changing.pk4");Files.copy(stored.toPath(),changing);
        boolean[] changed={false};boolean rejected=false;
        try {
            Pk4Checksum.read(changing.toFile(),true,(done,total)->{
                if(done>0 && !changed[0]) {
                    try { Files.write(changing,new byte[]{0},StandardOpenOption.APPEND); }
                    catch(IOException error) { throw new UncheckedIOException(error); }
                    changed[0]=true;
                }
                return true;
            });
        } catch(Pk4Checksum.Invalid expected) { rejected=expected.problem==Pk4Checksum.Problem.CHANGED_FILE; }
        require(changed[0] && rejected,"file changed during verification was accepted");
        scanner(root,args.length>1?args[1]:"");
        System.out.println("PASS: "+vectors+" native/Java MD4 vectors, "+archives+
            " complete archive checks, malformed/corrupt/duplicate/oversize rejection, bounded progress, cancellation/retry and changed-file recovery");
    }
}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    java_home = os.environ.get('JAVA_HOME', '')
    parser.add_argument('--javac', default=shutil.which('javac') or
                        (str(Path(java_home)/'bin/javac') if java_home else None))
    parser.add_argument('--cxx', default=shutil.which('clang++') or shutil.which('g++'))
    parser.add_argument('--retail-root', type=Path, help='also read and verify the supplied retail media, without modifying it')
    args = parser.parse_args()
    if not args.javac or not args.cxx:
        parser.error('a JDK and C++ compiler are required')
    (ROOT/'.tmp').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='android-retail-', dir=ROOT/'.tmp') as temporary:
        scratch=Path(temporary)
        probe=scratch/'native.cpp'
        probe.write_text('''#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <vector>
#include '''+json.dumps((ROOT/'src/idlib/hashing/MD4.cpp').as_posix())+'''
int main(){std::string path;while(std::getline(std::cin,path)){
    std::ifstream input(path,std::ios::binary);if(!input)return 2;
    std::vector<char> data((std::istreambuf_iterator<char>(input)),{});
    if(data.size()>262140)return 3;
    std::printf("%08x\\n",MD4_BlockChecksum(data.empty()?"":data.data(),static_cast<int>(data.size())));
}return 0;}
''')
        executable=scratch/('native.exe' if os.name=='nt' else 'native')
        subprocess.run([args.cxx,'-std=c++17',str(probe),'-o',str(executable)],check=True)
        vectors=[]
        for length in [*range(130),255,256,257,4096,65536,262140]:
            name=f'vector-{length}.bin'
            (scratch/name).write_bytes(bytes((i*17+length)&255 for i in range(length)))
            vectors.append(name)
        paths=[scratch/name for name in vectors]
        reference=subprocess.run([str(executable)],input=''.join(str(p)+'\n' for p in paths),
                                 capture_output=True,text=True,check=True).stdout.splitlines()
        assert len(reference)==len(vectors)
        (scratch/'vectors.tsv').write_text(''.join(f'{name}\t{value}\n' for name,value in zip(vectors,reference)))

        body=bytes(range(256))*600
        def create(name,compression,reverse=False):
            entries=[('folder/',b''),('empty.txt',b''),('alpha.bin',body),('omega.txt',b'Quake 4 verification')]
            if reverse: entries.reverse()
            with zipfile.ZipFile(scratch/name,'w',compression=compression) as archive:
                for entry,data in entries:archive.writestr(entry,data)
        create('stored.pk4',zipfile.ZIP_STORED)
        create('deflated.pk4',zipfile.ZIP_DEFLATED)
        create('reversed.pk4',zipfile.ZIP_STORED,True)
        with zipfile.ZipFile(scratch/'empty.pk4','w'):pass
        archives=[scratch/name for name in ('stored.pk4','deflated.pk4','reversed.pk4','empty.pk4')]
        engine=(ROOT/'src/framework/FileSystem.cpp').read_text()
        official_rows=re.findall(r'\{\s*"([^"]+\.pk4)",\s*(0x[0-9a-f]+),\s*(true|false),',engine)
        official={name.lower():int(value,16) for name,value,_ in official_rows}
        (scratch/'official.tsv').write_text(''.join(f'{name}\t{int(value,16):08x}\t{required}\n'
            for name,value,required in official_rows))
        language_table=engine.split('static const char *fsLanguagePackOrder[] = {',1)[1].split('};',1)[0]
        (scratch/'languages.txt').write_text(''.join(name+'\n' for name in re.findall(r'"([a-z]+)"',language_table)))
        if args.retail_root:
            archives += sorted(p for p in args.retail_root.resolve().iterdir()
                               if p.is_file() and p.suffix.lower()=='.pk4' and not p.name.lower().startswith('game'))
        archive_data=[]; crc_paths=[]
        for index,path in enumerate(archives):
            with zipfile.ZipFile(path) as archive:
                entries=archive.infolist()
                crcs=b''.join(struct.pack('<I',entry.CRC) for entry in entries if entry.file_size>0)
                archive_data.append((path,sum(entry.file_size for entry in entries)))
            crc_path=scratch/f'archive-{index}.bin';crc_path.write_bytes(crcs);crc_paths.append(crc_path)
        checksums=subprocess.run([str(executable)],input=''.join(str(p)+'\n' for p in crc_paths),
                                 capture_output=True,text=True,check=True).stdout.splitlines()
        assert len(checksums)==len(archives) and checksums[0]==checksums[1] and checksums[0]!=checksums[2]
        for (path,_),value in zip(archive_data,checksums):
            if path.name.lower() in official:assert int(value,16)==official[path.name.lower()],path.name
        (scratch/'archives.tsv').write_text(''.join(f'{path}\t{value}\t{size}\n'
            for (path,size),value in zip(archive_data,checksums)))
        (scratch/'invalid.pk4').write_bytes(b'not a zip archive'*4)
        original=(scratch/'stored.pk4').read_bytes()
        (scratch/'truncated.pk4').write_bytes(original[:-8])
        with zipfile.ZipFile(scratch/'duplicate.pk4','w') as archive:
            archive.writestr('case.txt',b'first');archive.writestr('CASE.TXT',b'second')
        with zipfile.ZipFile(scratch/'many-entries.pk4','w') as archive:
            for index in range(65536):archive.writestr(str(index),b'')
        corrupt=bytearray(original)
        with zipfile.ZipFile(scratch/'stored.pk4') as archive:position=archive.getinfo('alpha.bin').header_offset
        name_length,extra_length=struct.unpack_from('<HH',corrupt,position+26)
        corrupt[position+30+name_length+extra_length+3]^=255
        (scratch/'corrupt.pk4').write_bytes(corrupt)
        large=bytearray(original);position=large.index(b'PK\x01\x02')
        struct.pack_into('<I',large,position+24,0x80000000)
        (scratch/'large-entry.pk4').write_bytes(large)
        large=bytearray(original);end=large.rfind(b'PK\x05\x06')
        struct.pack_into('<I',large,end+12,16*1024*1024+1)
        (scratch/'large-directory.pk4').write_bytes(large)
        split=bytearray(original);struct.pack_into('<H',split,end+4,1)
        (scratch/'multi-disk.pk4').write_bytes(split)
        with zipfile.ZipFile(scratch/'expanded-limit.pk4','w') as archive:
            for index in range(5):archive.writestr(str(index),b'x')
        large=bytearray((scratch/'expanded-limit.pk4').read_bytes());position=0
        while True:
            position=large.find(b'PK\x01\x02',position)
            if position<0:break
            struct.pack_into('<I',large,position+24,0x7fffffff);position+=46
        (scratch/'expanded-limit.pk4').write_bytes(large)
        java_source=scratch/'RetailDataTest.java';java_source.write_text(JAVA)
        classes=scratch/'classes';classes.mkdir()
        javac=Path(args.javac).resolve();java=javac.with_name('java.exe' if os.name=='nt' else 'java')
        subprocess.run([str(javac),'--release','17','-d',str(classes),str(java_source),
                        *(str(ROOT/'mobile/android/app/src/main/java/com/darkmatter/openq4'/name)
                          for name in ('Pk4Checksum.java','RetailData.java'))],check=True)
        subprocess.run([str(java),'-cp',str(classes),'com.darkmatter.openq4.RetailDataTest',str(scratch),
                        str(args.retail_root.resolve()) if args.retail_root else ''],check=True)


if __name__=='__main__':main()
