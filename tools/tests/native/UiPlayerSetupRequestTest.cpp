// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#include "src/ui/retained/PlayerSetupRequest.h"
#include <cstdio>
#include <cstdlib>
#include <limits>

using namespace openq4::ui;
static unsigned checks=0;
static void Check(bool condition,const char* text) {
    ++checks; if (!condition) { std::fprintf(stderr,"FAIL: %s\n",text); std::exit(1); }
}
static StateValues Proposal(std::string field,StateValue value) {
    return {{"field",std::move(field)},{"value",std::move(value)},{"catalog",17.0},{"expected",std::string("observed")}};
}
int main() {
    std::string source,error;
    PlayerSetupRequest decoded;
    for (const auto& values: {Proposal("name",std::string("^1A\";quit")), Proposal("clan",std::string()),
                             Proposal("model",127.0),Proposal("page",-1.0),Proposal("rail",6.0),Proposal("rotation",247.5)}) {
        Check(EncodePlayerSetupRequest(values,source,error) && DecodePlayerSetupRequest(source,decoded,error),"typed proposal round-trips through production JSON transport");
        Check(decoded.value==values.at("value") && decoded.catalog==17 && decoded.expected=="observed","transport preserves exact input, observed source and catalog identity");
    }
    auto first=Proposal("name",std::string("first")), second=Proposal("name",std::string("second"));
    Check(EncodePlayerSetupRequest(first,source,error),"first queued field materializes its own payload");
    first["value"]=std::string("later GUI state");
    Check(DecodePlayerSetupRequest(source,decoded,error) && std::get<std::string>(decoded.value)=="first","later edits cannot rewrite an already queued proposal");
    for (const auto& invalid: {Proposal("name",std::string()),Proposal("name",std::string(24,'a')),Proposal("clan",std::string(13,'a')),
                              Proposal("name",std::string("a\nb")),Proposal("model",128.0),Proposal("model",-1.0),Proposal("model",.5),
                              Proposal("page",0.0),Proposal("page",2.0),Proposal("rail",7.0),Proposal("rotation",361.0),
                              Proposal("rotation",std::numeric_limits<double>::infinity()),Proposal("name",true),Proposal("exec",std::string("quit"))}) {
        const auto old=source;
        Check(!EncodePlayerSetupRequest(invalid,source,error) && source==old && !error.empty(),"invalid field refuses without publishing another payload");
    }
    for (double epoch:{0.0,-1.0,.5,4294967296.0,std::numeric_limits<double>::quiet_NaN()}) {
        auto invalid=Proposal("model",0.0); invalid["catalog"]=epoch;
        Check(!ResolvePlayerSetupRequest(invalid,decoded,error),"catalog identity is an exact positive bounded integer");
    }
    auto invalid=Proposal("name",std::string("valid")); invalid["extra"]=true;
    Check(!ResolvePlayerSetupRequest(invalid,decoded,error),"unknown proposal fields cannot enter the session");
    invalid=Proposal("model",0.0); invalid["expected"]=std::string(1025,'a');
    Check(!ResolvePlayerSetupRequest(invalid,decoded,error),"observed source is bounded independently of proposed value");
    for (const std::string& bad:std::vector<std::string>{"{}", "{\"field\":\"name\",\"field\":\"clan\",\"value\":\"x\",\"catalog\":1,\"expected\":\"\"}",
                               source+" quit",std::string(PlayerSetupRequestBytes+1,' ')}) {
        const auto previous=decoded.value;
        Check(!DecodePlayerSetupRequest(bad,decoded,error) && decoded.value==previous,"malformed/duplicate/trailing/oversized payload keeps the previous request untouched");
    }
    Action action; action.operation="player.setup.apply"; action.inputType=2;
    Expression field; field.type=2; field.literal=std::string("name");
    Expression value; value.type=2; value.inputValue=true;
    Expression catalog; catalog.type=0; catalog.state="setup.catalog";
    Expression expected; expected.type=2; expected.state="setup.observed_name";
    action.arguments={{"field",field},{"value",value},{"catalog",catalog},{"expected",expected}};
    Check(ValidPlayerSetupAction(action),"authored typed field action validates through the production adapter policy");
    auto changed=action; changed.arguments["value"].inputValue=false; changed.arguments["value"].state="mutable";
    Check(!ValidPlayerSetupAction(changed),"proposal values cannot become deferred GUI-state reads");
    changed=action; changed.arguments["catalog"].inputValue=true;
    Check(!ValidPlayerSetupAction(changed),"invocation input cannot impersonate the catalog epoch");
    changed=action; changed.arguments["field"].state="field";
    Check(!ValidPlayerSetupAction(changed),"field operation identity must remain an authored literal");
    changed=action; changed.arguments["field"].literal=3.0;
    Check(!ValidPlayerSetupAction(changed),"malformed compiled action refuses without throwing");
    std::printf("Player Setup proposals: %u checks passed\n",checks);
}
