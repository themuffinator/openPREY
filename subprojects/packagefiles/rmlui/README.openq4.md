# openQ4 RmlUi patches

The bundled [RmlUi 6.3](https://github.com/mikke89/RmlUi/tree/6.3) is distributed under its [MIT license](https://github.com/mikke89/RmlUi/blob/6.3/LICENSE.txt). Existing upstream ownership and licensing remain unchanged.

`focus-reveal-geometry.patch` adds a first-party openQ4 exact projected border-quad query, distributed under the same MIT license. It uses the existing accumulated transform and depth-plane conventions, rejects unavailable/nonfinite/nonpositive-w projections without changing output, and leaves `GetBoundingBox` unchanged. It does not clip the quad or guarantee that authored scroll ranges can reveal all ink. Callers must refresh geometry after layout before querying.

The separate existing `projection-geometry.patch` supplies that layout/transform refresh without rendering. `positioned-overflow.patch` retains positioned descendants in authored scroll extents. The new helper does not change either patch's semantics or add scroll range.

`masked-hit-test.patch` adds a first-party optional application predicate to
`Context::GetElementAtPoint`, under the same MIT license. The existing stacking
traversal passes it through recursive calls, so rejecting masked candidates also
exposes eligible elements behind them. Callers without a predicate retain the
original behavior. The predicate must not mutate the tree; openQ4 uses it to
evaluate ancestor mask geometry and semantic input eligibility in document space.

`hidden-presentation-update.patch` adds a first-party optional presentation
update mode, under the same MIT license. It updates a hidden parent's own style
but defers its `display:none` descendants until that parent is shown. openQ4
opts in only for canonical presentation documents with externally advanced
timelines and no controls, scrollbars, modals or pointer interaction. Ordinary
RmlUi contexts, CSS animations and widgets retain full updates. No authored
animation time is paused, and reveal resolves pending child styles before layout.

`suppressed-presentation-render.patch` adds a first-party, MIT-licensed optional
element paint predicate. openQ4 skips canonical local stacking contexts whose
isolated opacity is exactly zero, before traversing or compiling their artwork.
Layout, input and updates remain active, and ordinary RmlUi elements render as
before. A revealed subtree renders its current properties and animation phase.
