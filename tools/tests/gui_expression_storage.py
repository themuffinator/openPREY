#!/usr/bin/env python3
"""Check bounded, stable GUI operation storage and recursive conditional parsing."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import ui_legacy_expression as expressions

ROOT = Path(__file__).resolve().parents[2]
STORAGE_TEST = r'''
static void Storage() {
    for(int cycle=0;cycle<32;++cycle) {
        idWindow w;
        Check(sizeof(w.ops)<1024,"operation storage reserves the maximum inline");
        auto* first=w.ExpressionOp();
        first->d=42;
        for(int i=1;i<MAX_EXPRESSION_OPS;++i) {
            auto* next=w.ExpressionOp();
            Check(first==&w.ops[0],"append invalidated a parser operation pointer");
            Check(next->a==0 && next->b==0 && next->c==0 && next->d==0,"new operation is not zero initialized");
        }
        Check(first->d==42,"append changed an earlier operation");
        const int warnings=commonObject.warnings;
        Check(w.ExpressionOp()==first && w.numOps==MAX_EXPRESSION_OPS && w.ops.size()==MAX_EXPRESSION_OPS,
              "expression limit changed or storage grew past the limit");
        Check(commonObject.warnings==warnings+1,"overflow no longer warns");
        // @RESET@
        Check(w.ops.empty() && w.numOps==0,"reset retained operations");
        Check(w.ExpressionOp()->d==0,"reparse retained old operands");
    }
    commonObject.warnings=0;
    // Parsing the ':' arm appends enough operations to move contiguous
    // storage; the outer conditional's saved pointer must remain valid.
    for(const char* condition:{"0","1"}) {
        idWindow w;
        idParser p{{condition,TT_NUMBER},{"?",TT_PUNCTUATION},{"7",TT_NUMBER},{":",TT_PUNCTUATION},{"1",TT_NUMBER}};
        for(int i=0;i<80;++i){p.tokens.push_back({"+",TT_PUNCTUATION});p.tokens.push_back({"1",TT_NUMBER});}
        w.ParseExpression(&p);
        Check(w.ops.front().opType==WOP_TYPE_COND && w.ops.front().d==w.ops.back().c,
              "recursive conditional lost its false operand");
        Check(Evaluate(w,w.ops.front().d)==81,"recursive false-arm operations changed");
        // Check both choices with constants. Evaluation order for computed
        // false arms is an existing parser issue, independent of storage.
        idWindow constant;
        idParser q{{condition,TT_NUMBER},{"?",TT_PUNCTUATION},{"7",TT_NUMBER},{":",TT_PUNCTUATION},{"9",TT_NUMBER}};
        Check(Evaluate(constant,constant.ParseExpression(&q))==(condition[0]=='1'?7:9),"constant conditional changed");
    }
}
'''


def source():
    text=(ROOT/'src/ui/Window.cpp').read_text()
    header=(ROOT/'src/ui/Window.h').read_text()
    declaration=re.search(r'std::\w+<wexpOp_t> ops;',header)[0]
    # Run the actual reset statements from both reparse/teardown entry points.
    init=expressions.function(text,'void idWindow::CommonInit()')
    update=expressions.function(text,'bool idWindow::UpdateFromDictionary (')
    reset=re.search(r'ops\.clear\(\);\s*numOps = 0;',init)[0]
    assert re.search(r'ops\.clear\(\);\s*numOps = 0;',update)
    # The source suite includes the full production parser/evaluator, not a
    # reimplementation of conditional expressions.
    base=expressions.build_source().replace('std::deque<wexpOp_t> ops;',declaration)
    limit=re.search(r'const int MAX_EXPRESSION_OPS = (\d+);', (ROOT/'src/idlib/precompiled.h').read_text())[1]
    base=base.replace('MAX_EXPRESSION_OPS=256', 'MAX_EXPRESSION_OPS='+limit)
    extra=STORAGE_TEST.replace('// @RESET@',reset.replace('ops.', 'w.ops.').replace('numOps =', 'w.numOps ='))
    return base.replace('int main(){try{Missing();',extra+'\nint main(){try{Storage();Missing();')


def main():
    generated=source()
    scratch=ROOT/'.tmp/gui-expression-storage'
    scratch.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        env=dict(os.environ,TEMP=directory,TMP=directory,TMPDIR=directory)
        for name,text in (
            ('production',generated),
            ('moving_storage',generated.replace('std::deque<wexpOp_t> ops;','std::vector<wexpOp_t> ops;')),
            ('uncleared',generated.replace('w.ops.clear();','/* retained operations */')),
        ):
            cpp=Path(directory)/(name+'.cpp');exe=cpp.with_suffix('.exe' if os.name=='nt' else '')
            cpp.write_text(text)
            compiler=os.environ.get('CXX','clang++')
            conversion=['-Wno-null-conversion','-Wno-unused-private-field'] if 'clang' in Path(compiler).name else ['-Wno-conversion-null']
            subprocess.run([compiler,'-std=c++20','-Wall','-Wextra','-Werror',
                            '-Wno-unused-parameter','-Wno-unused-variable','-Wno-unused-function',
                            '-Wno-overloaded-virtual','-Wno-missing-field-initializers',*conversion,str(cpp),'-o',str(exe)],
                           cwd=directory,env=env,check=True)
            run=subprocess.run([str(exe)],cwd=directory,env=env,text=True,capture_output=True)
            if name=='production':
                assert run.returncode==0,run.stdout+run.stderr
                print(run.stdout.strip())
            else:
                assert run.returncode!=0 and 'FAIL' in run.stderr,run
                print(name+': rejected ('+run.stderr.strip()+')')


if __name__=='__main__':
    main()
