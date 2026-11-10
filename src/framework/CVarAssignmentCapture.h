// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#pragma once
#include <cstddef>
#include <string_view>

namespace openq4 {
// Observe accepted setter calls on this thread without allocations or writes.
// Unlike modified flags this includes assigning the current value. The caller
// keeps the bounded names/flags alive; nested captures observe the same calls.
class CVarAssignmentCapture {
public:
 CVarAssignmentCapture() noexcept = default;
 ~CVarAssignmentCapture() { End(); }
 CVarAssignmentCapture(const CVarAssignmentCapture&) = delete;
 CVarAssignmentCapture& operator=(const CVarAssignmentCapture&) = delete;
 void Begin(const char* const* names,std::size_t count,bool* assigned) noexcept {
  End();if(!names||!assigned||!count)return;
  names_=names;count_=count;assigned_=assigned;
  for(std::size_t i=0;i<count_;++i)assigned_[i]=false;
  previous_=active_;active_=this;
 }
 void End() noexcept {
  if(!assigned_)return;
  auto** link=&active_;
  while(*link&&*link!=this)link=&(*link)->previous_;
  if(*link)*link=previous_;
  names_=nullptr;assigned_=nullptr;count_=0;previous_=nullptr;
 }
 static void Record(std::string_view name) noexcept {
  for(auto* capture=active_;capture;capture=capture->previous_){
   for(std::size_t i=0;i<capture->count_;++i){
    if(capture->names_[i]&&Equal(name,capture->names_[i]))capture->assigned_[i]=true;
   }
  }
 }
 static void Record(const char* name) noexcept {
  if(active_&&name)Record(std::string_view(name));
 }
private:
 static bool Equal(std::string_view a,std::string_view b) noexcept {
  if(a.size()!=b.size())return false;
  const auto lower=[](unsigned char c){return c>='A'&&c<='Z'?c+('a'-'A'):c;};
  for(std::size_t i=0;i<a.size();++i)if(lower(a[i])!=lower(b[i]))return false;
  return true;
 }
 inline static thread_local CVarAssignmentCapture* active_=nullptr;
 CVarAssignmentCapture* previous_=nullptr;
 const char* const* names_=nullptr;
 bool* assigned_=nullptr;
 std::size_t count_=0;
};
}
