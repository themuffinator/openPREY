#include <algorithm>
#include <cctype>
#include <cstdio>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#include "src/idlib/ContentIdentity.h"
#ifdef _WIN32
#include <malloc.h>
#define _alloca16 _alloca
#else
#include <alloca.h>
#define _alloca16 alloca
#endif
#define MEM_SCOPED_TAG(a,b)
static void Check(bool ok) { if (!ok) throw std::runtime_error("dictionary identity failure"); }
struct idStr : std::string {
    using std::string::string;
    operator const char*() const { return c_str(); }
    int Icmp(const char* other) const {
        std::string a=*this,b=other;
        for (char& c:a) c=static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
        for (char& c:b) c=static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
        return a.compare(b);
    }
};
struct idStrPool;
struct idPoolStr : idStr {
    idStrPool* pool; int users=1;
    idPoolStr(idStrPool* p,const char* text) : idStr(text),pool(p) {}
    const idStrPool* GetPool() const { return pool; }
};
struct idStrPool {
    bool insensitive=false;
    std::vector<const idPoolStr*> strings;
    const idPoolStr* CopyString(const idPoolStr* value) { ++const_cast<idPoolStr*>(value)->users; return value; }
    const idPoolStr* AllocString(const char* text) {
        for (auto* s:strings) if (insensitive ? s->Icmp(text)==0 : *s==text) return CopyString(s);
        auto* value=new idPoolStr(this,text); strings.push_back(value); return value;
    }
    void FreeString(const idPoolStr* value) {
        if (--const_cast<idPoolStr*>(value)->users==0) {
            strings.erase(std::find(strings.begin(),strings.end(),value)); delete value;
        }
    }
};
template<class T> struct List : std::vector<T> {
    int Num() const { return static_cast<int>(this->size()); }
    void SetNum(int n) { this->resize(n); }
    void Clear() { this->clear(); }
    int Append(const T& item) { this->push_back(item); return Num()-1; }
    void RemoveIndex(int i) { this->erase(this->begin()+i); }
};
struct Hash {
    int count=0;
    int GenerateKey(const char*,bool) const { return 0; }
    void Add(int,int index) { count=std::max(count,index+1); }
    int First(int) const { return count ? 0 : -1; }
    int Next(int index) const { return index+1<count ? index+1 : -1; }
    void RemoveIndex(int,int) { --count; }
    void Free() { count=0; }
};
struct idKeyValue {
    const idPoolStr *key=nullptr,*value=nullptr;
    const idStr& GetKey() const { return *key; }
    const idStr& GetValue() const { return *value; }
};
struct ErrorSink {
    void DWarning(const char*) {}
    [[noreturn]] void FatalError(const char*) { throw std::runtime_error("pool boundary"); }
} sink;
static ErrorSink* common=&sink;
struct idLib { static inline ErrorSink* common=&sink; };
struct idDict {
    idContentIdentity contentIdentity;
    List<idKeyValue> args; Hash argHash;
    static inline idStrPool globalKeys,globalValues;
    static inline bool globalPoolsShutdown=false;
    idDict() = default;
    idDict(const idDict& other) { *this=other; }
    ~idDict() { Clear(); }
    idDict& operator=(const idDict&);
    void Copy(const idDict&); void TransferKeyValues(idDict&); void SetDefaults(const idDict*);
    void Clear(); void Set(const char*,const char*); void Delete(const char*);
    int FindKeyIndex(const char*) const;
    const idKeyValue* FindKey(const char*) const;
};
#include "DictIdentityUnderTest.inc"
int main() {
    idDict::globalKeys.insensitive=true;
    {
        idDict a,b; a.Set("Key","first"); b.Set("other","second");
        idContentObserver observer,other;
        auto observe=[&] { observer.Attach(a.contentIdentity); Check(observer.Matches(a.contentIdentity)); };
        auto invalid=[&] { Check(!observer.Matches(a.contentIdentity)); };
        observe(); a.Set("key","other"); invalid(); Check(a.FindKey("key")->GetValue()=="other");
        observe(); a.Set("added","value"); invalid();
        observe(); a.Delete("ADDED"); invalid();
        observe(); a.Copy(b); invalid(); Check(a.FindKey("other"));
        b.Set("new","default"); observe(); a.SetDefaults(&b); invalid(); Check(a.FindKey("new"));
        observe(); a=b; invalid();
        observe(); other.Attach(b.contentIdentity); a.TransferKeyValues(b); invalid();
        Check(!other.Matches(b.contentIdentity) && b.args.empty());
        observe(); idDict copy(a); Check(observer.Matches(a.contentIdentity));
        other.Attach(copy.contentIdentity); copy.Set("new","changed");
        Check(!other.Matches(copy.contentIdentity) && observer.Matches(a.contentIdentity));
        a.Clear(); invalid();
        // A source destroyed and rebuilt at the same address cannot match.
        observe(); a.~idDict(); new (&a) idDict; invalid();
        observe(); other.Attach(a.contentIdentity); invalid();
        Check(other.Matches(a.contentIdentity)); other.Clear();
        observe(); { idContentObserver temporary; temporary.Attach(a.contentIdentity); }
        a.Set("after-observer-destruction","safe"); invalid();
        observe(); a=a; Check(observer.Matches(a.contentIdentity));
        a.Copy(a); a.TransferKeyValues(a); Check(observer.Matches(a.contentIdentity));
        // Empty/no-op key edits cannot fabricate an identity match.
        a.Set("", "ignored"); a.Delete("missing"); Check(observer.Matches(a.contentIdentity));
    }
    Check(idDict::globalKeys.strings.empty() && idDict::globalValues.strings.empty());
    std::puts("Production dictionary mutations, observer/source lifetime, copying and replacement passed");
}
