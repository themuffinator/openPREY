// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#pragma once
#include "Motion.h"
#include <cstdint>

namespace openq4::ui {

// Evaluate a compiled expression as bounded typed data, without changing its
// variables or the previous result on failure. Unselected branches stay lazy.
bool EvaluateStateExpression(const Expression& expression, const StateValues& variables,
	StateValue& value, std::string& error, const PresentationLookup& presentation = {},
	const StateValue* input = nullptr);

struct PresentationCell {
	PresentationValue value;
	bool expressionDisabled = false;
	bool pending = false; // Transient write awaiting the next expression evaluation.
};
struct PresentationPropertyOverride {
	Value value;
	bool expressionDisabled = false;
};
struct StatePresentationSnapshot {
	std::map<std::string,PresentationCell> variables;
	std::map<PropertyKey,PresentationPropertyOverride> properties;
};

// Application and host batches commit together with all derived properties.
// Evaluating expressions never executes commands or changes authored source.
class State {
public:
	// Keeps a copy of the model's declarations, bindings and controls.
	bool Reset(const DocumentModel& model, std::string& error);
	// References the shared model's declarations, bindings and controls
	// instead: the model outlives this state and its copies.
	bool Reset(std::shared_ptr<const DocumentModel> model, std::string& error);
	bool Set(const StateValues& changes, std::string& error, bool hostSources = false);
	// Whether Set(changes) would do more than accept the batch: a value
	// differs, a presentation write awaits evaluation, or the batch is invalid.
	bool WouldChange(const StateValues& changes, bool hostSources = false) const;
	// Event entry refreshes pending application and current host values in one
	// evaluation; neither batch can expose an invalid intermediate binding.
	bool SetCombined(const StateValues& application, const StateValues& hostSources, std::string& error);
	// Full instance restore evaluates application and current host snapshots in
	// one transaction, without an invalid intermediate binding evaluation.
	bool Restore(const StateValues& application, const StateValues& hostSources, std::string& error,
		const StatePresentationSnapshot* presentation = nullptr);
	bool WritePresentationVariable(const std::string& id, const PresentationValue& value,
		bool overrideExpression, std::string& error);
	// All members must be binding-owned properties. Stage multi-property writes
	// together; overrideExpression=false never revives a disabled expression.
	bool OverrideProperties(const PropertyValues& values, bool overrideExpression, std::string& error);
	const StatePresentationSnapshot& Presentation() const { return presentation; }
	const StateValues& Variables() const { return variables; }
	const PropertyValues& Properties() const { return properties; }
	const std::map<std::string,bool>& Enabled() const { return enabled; }
	const std::map<std::string,ControlReadback>& ControlValues() const { return controlValues; }
	const std::map<std::string,StateDeclaration>& Declarations() const { return *declarations; }
	std::uint64_t Revision() const { return revision; }
	// The bound properties whose values changed since the last call, appended
	// to `keys`; false when every property must be treated as changed (a full
	// evaluation, a reset or a restore since then).
	bool TakeChangedProperties(std::vector<PropertyKey>& keys);
private:
	bool Evaluate(const StateValues& candidate, PropertyValues& props, std::map<std::string,bool>& controls,
		StatePresentationSnapshot& output, std::map<std::string,ControlReadback>& readbacks, std::string& error) const;
	// openQ4: re-evaluate only the bindings that read a changed variable,
	// in place once every evaluation has succeeded.
	bool SetIncremental(const StateValues& overlay, std::string& error);
	bool EvaluateDerived(const StateValues& base, const StateValues* overlay, StatePresentationSnapshot& output,
		std::map<std::string,ControlReadback>& readbacks, std::string& error) const;
	void MarkAllChanged() { changedProperties.clear(); allPropertiesChanged = true; }
	// The document's declarations and bindings are fixed after Reset and
	// shared by copies: a transactional copy duplicates only live values.
	// They are the shared model's, which `model` keeps.
	std::shared_ptr<const DocumentModel> model;
	std::shared_ptr<const std::map<std::string,StateDeclaration>> declarations = std::make_shared<const std::map<std::string,StateDeclaration>>();
	std::shared_ptr<const std::vector<Binding>> bindings = std::make_shared<const std::vector<Binding>>();
	// For each state variable, the bindings whose expressions read it.
	std::shared_ptr<const std::map<std::string,std::vector<std::size_t>>> dependents =
		std::make_shared<const std::map<std::string,std::vector<std::size_t>>>();
	std::shared_ptr<const std::map<std::string,PresentationVariable>> presentationDeclarations = std::make_shared<const std::map<std::string,PresentationVariable>>();
	StatePresentationSnapshot presentation;
	StateValues variables;
	PropertyValues properties;
	std::map<std::string,bool> enabled;
	// The value controls (not buttons or scrollbars) by ID, in the model.
	std::shared_ptr<const std::map<std::string,const Control*>> controlDeclarations = std::make_shared<const std::map<std::string,const Control*>>();
	std::shared_ptr<const std::vector<const ModelSceneSpec*>> modelDeclarations = std::make_shared<const std::vector<const ModelSceneSpec*>>();
	std::map<std::string,ControlReadback> controlValues;
	std::uint64_t revision = 0;
	bool presentationDirty = false;
	std::vector<PropertyKey> changedProperties;
	bool allPropertiesChanged = true;
};

} // namespace openq4::ui
