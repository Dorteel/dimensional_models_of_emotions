// Create Domain Model tab self-test (?selftest=1&create=1). The test server saves into a temporary
// domains folder (gui/tests/test_browser.py), never into the repository's domains/.
// Fills the form with DOM input events, checks validation feedback, the catalogue/dictionary
// integration, dimension reordering, the preview plot, saving and overwrite confirmation.
// Returns the saved result and the validated model so the Python test can inspect the files.

export async function runCreateChecks(dashboard, check) {
  document.querySelector("#tab-create").click();
  const tab = dashboard.tabs.create;
  await tab.ready;
  const q = (sel) => tab.el.querySelector(sel);
  const field = (name) => q(`.form-pane [data-field="${CSS.escape(name)}"]`);
  const type = async (name, value) => {
    const input = field(name);
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
  };
  const validate = () => tab.validate();
  const errorFields = () => (tab.lastCheck?.errors || []).map((e) => e.field);
  const click = (sel) => q(sel).click();

  tab.update({ name: "", description: "", notes: "", dimensions: [], emotions: [] });
  await validate();
  check("Create: an empty form reports the missing name and dimensions, and Save is disabled",
        errorFields().includes("name") && errorFields().includes("dimensions") && q('[data-role="save"]').disabled,
        errorFields().join(", "));

  // ---------------------------------------------------------------- step 1
  await type("name", "GUI Selftest Model");
  await type("description", 'A model "created" in the GUI self-test.\nSecond line.');
  await type("notes", "Self-test notes\twith a tab");
  await validate();
  check("Create: the model ID is the builder's SafeID of the name",
        tab.lastCheck.model_id === "gui_selftest_model" && q('[data-role="model-id"]').textContent.includes("gui_selftest_model"));
  check("Create: the destination is domains/<model_id>/<model_id>.yaml and .ods",
        /gui_selftest_model\/gui_selftest_model\.yaml/.test(q('[data-role="destination"]').textContent) &&
        /gui_selftest_model\/gui_selftest_model\.ods/.test(q('[data-role="destination"]').textContent));

  // ---------------------------------------------------------------- step 2
  click('[data-role="add-dimension"]');
  click('[data-role="add-dimension"]');
  await type("dimensions.0.name", "Valence");
  await type("dimensions.0.definition", "Pleasantness of the emotion.");
  await type("dimensions.0.min", "-1");
  await type("dimensions.0.max", "1");
  await type("dimensions.1.name", "Arousal");
  await type("dimensions.1.definition", "Activation of the emotion.");
  await type("dimensions.1.min", "5");
  await type("dimensions.1.max", "1");
  await validate();
  check("Create: minimum >= maximum is reported on the dimension's maximum field",
        errorFields().includes("dimensions.1.max") && field("dimensions.1.max").classList.contains("invalid"));
  await type("dimensions.1.min", "0");
  const circ = field("dimensions.1.circular");
  circ.value = "yes";
  circ.dispatchEvent(new Event("change", { bubbles: true }));
  await type("dimensions.1.name", "valence");
  await validate();
  check("Create: duplicate dimension names are reported", errorFields().includes("dimensions.1.name"));
  await type("dimensions.1.name", "Arousal");
  await validate();
  check("Create: dimension IDs follow SafeID", tab.lastCheck.model.dimensions.map((d) => d.id).join() === "valence,arousal" &&
        q('[data-role="dim-id-1"]').textContent === "id: arousal");

  // ---------------------------------------------------------------- step 3: catalogue emotion + dictionary definition
  check("Create: an emotion that is not in the catalogue is not added from it", tab.addFromCatalogue("No Such Emotion") === false);
  q('[data-role="catalogue-input"]').value = "Joy";
  click('[data-role="add-catalogue"]');
  const joy = tab.catalogue.find((e) => e.name === "Joy");
  check("Create: a catalogue emotion keeps its name and Concept ID (name read-only)",
        tab.state.emotions[0].concept_id === joy.concept_id && field("emotions.0.name").readOnly &&
        q(".entry.emotion .badge").textContent.includes(joy.concept_id));
  const pick = q('select[data-role="dictionary-definition"]');
  check("Create: the emotion dictionary's definitions are offered", pick && pick.options.length === joy.definitions.length + 1,
        `${joy.definitions.length} definitions`);
  pick.value = "0";
  pick.dispatchEvent(new Event("change", { bubbles: true }));
  check("Create: choosing a dictionary definition copies it verbatim and records its source in the notes",
        field("emotions.0.definition").value === joy.definitions[0].text &&
        field("emotions.0.notes").value.includes(joy.definitions[0].source));
  await type("emotions.0.coordinates.0", "2");
  await type("emotions.0.coordinates.1", "0.5");
  await validate();
  check("Create: a coordinate outside the dimension's range is reported on that coordinate",
        errorFields().includes("emotions.0.coordinates.0"));
  await type("emotions.0.coordinates.0", "0.1234567890123456");
  await validate();
  check("Create: a coordinate beyond ODS's lossless precision is reported (as the builder's YAMLNumber refuses it)",
        tab.lastCheck.errors.some((e) => e.field === "emotions.0.coordinates.0" && /precision/.test(e.message)));
  await type("emotions.0.coordinates.0", "0.8");

  // new emotion
  click('[data-role="add-new"]');
  await type("emotions.1.name", "Selftest Calm");
  await type("emotions.1.definition", "A calm state defined in the self-test.");
  await type("emotions.1.coordinates.0", "-0.5");
  await type("emotions.1.coordinates.1", "0.1");
  await validate();
  check("Create: a new emotion is accepted with a note that population needs it in the dictionary",
        !tab.lastCheck.errors.length && tab.lastCheck.warnings.some((w) => w.field === "emotions.1.name") &&
        tab.lastCheck.model.emotions[1].id === "selftest_calm", JSON.stringify(tab.lastCheck.errors));

  // reorder keeps coordinates with their dimension
  q('button[data-action="dimension-up"][data-index="1"]').click();
  const moved = tab.state.dimensions[0].name === "Arousal" && field("emotions.0.coordinates.0").value === "0.5" &&
                field("emotions.0.coordinates.1").value === "0.8";
  q('button[data-action="dimension-up"][data-index="1"]').click();
  check("Create: reordering dimensions moves every emotion's coordinates with them", moved &&
        tab.state.dimensions[0].name === "Valence" && field("emotions.0.coordinates.0").value === "0.8");

  // preview reuses the coordinate plot
  const pts = [...tab.preview.svg.querySelectorAll(".pt")].map((g) => JSON.parse(g.dataset.values));
  check("Create: the preview plots the emotions at their coordinates", tab.preview.svg.dataset.mode === "2d" &&
        JSON.stringify(pts) === JSON.stringify([["0.8", "0.5"], ["-0.5", "0.1"]]), JSON.stringify(pts));

  // reserved names
  await type("name", "circumplex");
  await validate();
  check("Create: a reference model's name cannot be used", errorFields().includes("name"));
  await type("name", "GUI Selftest Model");
  await validate();
  check("Create: the complete model is valid and Save is enabled", !tab.lastCheck.errors.length && !q('[data-role="save"]').disabled,
        JSON.stringify(tab.lastCheck.errors));

  // ---------------------------------------------------------------- save, then overwrite with/without confirmation
  const expected = tab.lastCheck.model;
  const originalConfirm = window.confirm;
  let asked = 0;
  const first = await tab.save();
  check("Create: saving writes the model with the builder macros", first.ok && first.model_id === "gui_selftest_model" &&
        !first.replaced.length && q(".save-result")?.textContent.includes("populate_ontology.py --domains gui_selftest_model"),
        first.ok ? first.yaml : JSON.stringify(first.errors));
  try {
    window.confirm = () => { asked += 1; return false; };
    const declined = await tab.save();
    check("Create: saving over an existing model asks first; declining keeps the files", asked === 1 && declined.needs_confirmation &&
          /existing files kept/.test(q('[data-role="state"]').textContent));
    await type("notes", "Self-test notes, second version");
    window.confirm = () => { asked += 1; return true; };
    const second = await tab.save();
    check("Create: confirming replaces both files", asked === 2 && second.ok && second.replaced.length === 2);
    await tab.validate();
    check("Create: after saving, the destination shows that the model exists",
          /Exists/.test(q('[data-role="destination"]').textContent));
    return { saved: second, expected: tab.lastCheck.model, first: { yaml_text: first.yaml_text }, expectedFirst: expected };
  } finally {
    window.confirm = originalConfirm;
  }
}
