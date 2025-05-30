import streamlit as st
import pandas as pd
import pulp

# Initialize session state for storing data and results
if "ingredients_df" not in st.session_state:
    st.session_state.ingredients_df = None
if "diet" not in st.session_state:
    st.session_state.diet = {}
if "total_cost" not in st.session_state:
    st.session_state.total_cost = 0
if "nutritional_values" not in st.session_state:
    st.session_state.nutritional_values = {}
if "compliance_data" not in st.session_state:
    st.session_state.compliance_data = []
if "recommendations" not in st.session_state:
    st.session_state.recommendations = []

# Display the logo image before the title, centered, larger, and without caption
try:
    # Use columns to center the image
    col1, col2, col3 = st.columns([1, 2, 1])  # Create three columns, middle one wider
    with col2:  # Place the image in the middle column to center it
        st.image("C:/Users/diego/Downloads/APP-NEGOCIO/nombre_archivo_logo.png", width=300)  # Increased width to 300
except Exception as e:
    st.warning(f"No se pudo cargar la imagen del logo: {str(e)}. Verifica la ruta del archivo.")

# Title of the app, now below the image
st.title("Formulador de Dietas para Monogástricos")

# File uploader for Excel file
uploaded_file = st.file_uploader("Carga el archivo Excel con los ingredientes", type=["xlsx"])

# Function to run the optimization
def run_optimization(ingredients_df, selected_species, selected_stage, req, energy_col, all_nutrients):
    try:
        prob = pulp.LpProblem("Diet_Formulation", pulp.LpMinimize)
        ingredient_vars = pulp.LpVariable.dicts("Ing", ingredients_df.index, lowBound=0, upBound=1, cat="Continuous")
        
        # Objective: minimize cost
        prob += pulp.lpSum([ingredients_df.loc[i, "Costo"] * ingredient_vars[i] for i in ingredients_df.index]), "Total_Cost"
        
        # Constraint: total proportion must be 1 (100%)
        prob += pulp.lpSum([ingredient_vars[i] for i in ingredients_df.index]) == 1, "Total_Proportion"
        
        # Constraints: nutritional requirements (exact minimums)
        for nutrient in all_nutrients:
            required_value = req["Energía" if nutrient == energy_col else nutrient]
            if required_value != "NA" and not pd.isna(required_value):
                required_value = float(required_value)
                prob += (
                    pulp.lpSum([ingredients_df.loc[i, nutrient] * ingredient_vars[i] for i in ingredients_df.index])
                    >= required_value,
                    f"Min_{nutrient}"
                )
        
        # Constraints: maximum inclusion limits
        max_inclusion_col = "Max_Inclusion_Aves" if selected_species == "Aves" else "Max_Inclusion_Cerdos"
        for i in ingredients_df.index:
            max_limit = ingredients_df.loc[i, max_inclusion_col]
            if not pd.isna(max_limit):
                prob += ingredient_vars[i] <= max_limit / 100, f"Max_Inclusion_{i}"
        
        # Solve the problem
        prob.solve()
        
        # Extract the solution
        diet = {}
        total_cost = 0
        nutritional_values = {nutrient: 0 for nutrient in all_nutrients}
        
        if pulp.LpStatus[prob.status] == "Optimal":
            for i in ingredients_df.index:
                amount = ingredient_vars[i].varValue * 100
                if amount > 0:
                    ingredient_name = ingredients_df.loc[i, "Ingrediente"]
                    diet[ingredient_name] = amount
                    total_cost += ingredients_df.loc[i, "Costo"] * (amount / 100) * 100
                    for nutrient in all_nutrients:
                        nutritional_values[nutrient] += ingredients_df.loc[i, nutrient] * (amount / 100)
        else:
            st.warning("La optimización no encontró una solución factible con los datos actuales.")
            return {}, 0, {}, [], []  # Return empty values if infeasible
        
        # Generate compliance data and recommendations
        compliance_data = []
        recommendations = []
        for nutrient in all_nutrients:
            display_nutrient = "Energía" if nutrient.startswith("Energía_") else nutrient
            required_value = req[display_nutrient]
            achieved_value = nutritional_values[nutrient]
            if required_value != "NA" and not pd.isna(required_value):
                required_value = float(required_value)
                status = "Cumple" if achieved_value >= required_value else "No Cumple"
                compliance_data.append({
                    "Nutriente": display_nutrient,
                    "Requerido": required_value,
                    "Obtenido": round(achieved_value, 2),
                    "Estado": status
                })
                if achieved_value < required_value:
                    rec = f"**{display_nutrient} insuficiente**: "
                    if display_nutrient == "Energía":
                        rec += "Considera agregar 'MAIZ NACIONAL' (alto en energía) o 'ACEITE de SOJA'."
                    elif display_nutrient == "PB":
                        rec += "Incluye 'HARINA de SOJA 47% PB' o 'HARINA de PESCADO' para aumentar la proteína."
                    elif display_nutrient == "Ca":
                        rec += "Agrega 'CARBONATO de CALCIO' para mejorar el calcio."
                    elif display_nutrient == "P":
                        rec += "Incluye 'FOSFATO DICALCICO 18% P' para aumentar el fósforo."
                    elif display_nutrient == "Na":
                        rec += "Aumenta 'SAL' (máximo 0.5% para aves, ajusta si necesario) o usa 'CLORURO de SODIO'."
                    elif display_nutrient == "Cl":
                        rec += "Aumenta 'SAL' o considera 'CLORURO de SODIO'."
                    elif display_nutrient == "LYS":
                        rec += "Agrega 'L-LISINA HCl' para mejorar la lisina."
                    elif display_nutrient == "MET":
                        rec += "Incluye 'L-METIONINA' para aumentar la metionina."
                    recommendations.append(rec)
            else:
                compliance_data.append({
                    "Nutriente": display_nutrient,
                    "Requerido": "NA",
                    "Obtenido": round(achieved_value, 2),
                    "Estado": "No Aplica"
                })
        
        return diet, total_cost, nutritional_values, compliance_data, recommendations
    except Exception as e:
        st.error(f"Error durante la optimización: {str(e)}")
        return {}, 0, {}, [], []

if uploaded_file is not None:
    try:
        # Load the Excel file only if not already loaded
        if st.session_state.ingredients_df is None:
            ingredients_df = pd.read_excel(uploaded_file, sheet_name="Ingredientes")
            requirements_df = pd.read_excel(uploaded_file, sheet_name="Requerimientos")
            st.session_state.ingredients_df = ingredients_df.copy()
        else:
            ingredients_df = st.session_state.ingredients_df.copy()
            requirements_df = pd.read_excel(uploaded_file, sheet_name="Requerimientos")

        # Store original data
        original_ingredients_df = ingredients_df.copy()

        # Validate required columns in Ingredients sheet
        required_ingredient_cols = ["Ingrediente", "Costo", "Energía_Aves_Pollitos", "Energía_Aves_Pollos", "Energía_Cerdos_Crecimiento", "Energía_Cerdos_Cerdas", "PB", "Ca", "P", "Na", "Cl", "LYS", "MET", "Max_Inclusion_Aves", "Max_Inclusion_Cerdos"]
        missing_cols = [col for col in required_ingredient_cols if col not in ingredients_df.columns]
        if missing_cols:
            st.error(f"Faltan columnas en la hoja 'Ingredientes': {', '.join(missing_cols)}. Verifica el archivo Excel.")
            st.stop()

        # Validate required columns in Requirements sheet
        required_requirement_cols = ["Especie", "Etapa", "Energía", "PB", "Ca", "P", "Na", "Cl", "LYS", "MET"]
        if not all(col in requirements_df.columns for col in required_requirement_cols):
            st.error("Faltan columnas en la hoja 'Requerimientos'. Se requieren: " + ", ".join(required_requirement_cols))
            st.stop()

        # Ensure numeric columns are properly formatted
        numeric_cols = ["Costo", "Energía_Aves_Pollitos", "Energía_Aves_Pollos", "Energía_Cerdos_Crecimiento", "Energía_Cerdos_Cerdas", "PB", "Ca", "P", "Na", "Cl", "LYS", "MET", "Max_Inclusion_Aves", "Max_Inclusion_Cerdos"]
        for col in numeric_cols:
            ingredients_df[col] = pd.to_numeric(ingredients_df[col], errors="coerce")
            st.session_state.ingredients_df[col] = pd.to_numeric(st.session_state.ingredients_df[col], errors="coerce")

        # Display available species and stages
        species = requirements_df["Especie"].unique()
        selected_species = st.selectbox("Selecciona la especie", species)

        # Filter stages based on selected species
        stages = requirements_df[requirements_df["Especie"] == selected_species]["Etapa"].unique()
        selected_stage = st.selectbox("Selecciona la etapa", stages)

        # Get requirements for the selected species and stage
        req = requirements_df[(requirements_df["Especie"] == selected_species) & (requirements_df["Etapa"] == selected_stage)].iloc[0]

        # Determine the appropriate energy column based on species and stage
        energy_col = None
        if selected_species == "Aves":
            energy_col = "Energía_Aves_Pollitos" if selected_stage == "Pollitos" else "Energía_Aves_Pollos"
        elif selected_species == "Cerdos":
            energy_col = "Energía_Cerdos_Crecimiento" if selected_stage == "Crecimiento" else "Energía_Cerdos_Cerdas"
        if not energy_col or energy_col not in ingredients_df.columns:
            st.error(f"Columna de energía no encontrada para {selected_species} - {selected_stage}. Verifica las columnas en el Excel.")
            st.stop()

        # Allow user to select ingredients
        all_ingredients = ingredients_df["Ingrediente"].tolist()
        selected_ingredients = st.multiselect("Selecciona los ingredientes para la formulación", all_ingredients, default=all_ingredients)

        if not selected_ingredients:
            st.warning("Por favor, selecciona al menos un ingrediente para continuar.")
            st.stop()

        # Filter ingredients based on user selection
        filtered_df = ingredients_df[ingredients_df["Ingrediente"].isin(selected_ingredients)].copy()

        # Nutrients to optimize
        nutrients = ["PB", "Ca", "P", "Na", "Cl", "LYS", "MET"]
        all_nutrients = [energy_col] + nutrients

        # Run initial optimization
        if st.session_state.diet == {} or st.button("Recalcular Dieta"):
            diet, total_cost, nutritional_values, compliance_data, recommendations = run_optimization(
                filtered_df, selected_species, selected_stage, req, energy_col, all_nutrients
            )
            st.session_state.diet = diet
            st.session_state.total_cost = total_cost
            st.session_state.nutritional_values = nutritional_values
            st.session_state.compliance_data = compliance_data
            st.session_state.recommendations = recommendations

        # Composition view and edit section
        with st.expander("Ver/Modificar Composición de Materias Primas"):
            st.write("### Composición Actual")
            st.dataframe(filtered_df[["Ingrediente", "Costo", energy_col, "PB", "Ca", "P", "Na", "Cl", "LYS", "MET"]])

            st.write("### Editar Composición")
            editable_columns = ["Ingrediente", "Costo", energy_col, "PB", "Ca", "P", "Na", "Cl", "LYS", "MET"]
            with st.form(key=f"edit_form_{selected_species}_{selected_stage}"):
                # Use the filtered DataFrame for editing
                edited_df = st.data_editor(
                    filtered_df[editable_columns],
                    column_config={
                        "Ingrediente": st.column_config.TextColumn("Ingrediente", disabled=True),
                        "Costo": st.column_config.NumberColumn("Costo (€/kg)", disabled=True, format="%.2f"),
                        energy_col: st.column_config.NumberColumn(f"{energy_col} (kcal/kg)", min_value=0, step=10),
                        "PB": st.column_config.NumberColumn("PB (%)", min_value=0, step=0.1),
                        "Ca": st.column_config.NumberColumn("Ca (%)", min_value=0, step=0.01),
                        "P": st.column_config.NumberColumn("P (%)", min_value=0, step=0.01),
                        "Na": st.column_config.NumberColumn("Na (%)", min_value=0, step=0.01),
                        "Cl": st.column_config.NumberColumn("Cl (%)", min_value=0, step=0.01),
                        "LYS": st.column_config.NumberColumn("LYS (%)", min_value=0, step=0.01),
                        "MET": st.column_config.NumberColumn("MET (%)", min_value=0, step=0.01)
                    },
                    disabled=["Ingrediente", "Costo"],
                    key=f"editor_{selected_species}_{selected_stage}"
                )

                # Submit button for the form
                submitted = st.form_submit_button("Guardar Cambios")
                if submitted:
                    # Apply the edited values to the main DataFrame
                    for col in editable_columns:
                        if col not in ["Ingrediente", "Costo"]:  # Skip non-editable columns
                            ingredients_df.loc[filtered_df.index, col] = edited_df[col]
                            st.session_state.ingredients_df.loc[filtered_df.index, col] = edited_df[col]
                            filtered_df.loc[:, col] = edited_df[col]

                    st.success("Cambios guardados. Recalculando la dieta...")

                    # Re-run optimization with updated data
                    diet, total_cost, nutritional_values, compliance_data, recommendations = run_optimization(
                        filtered_df, selected_species, selected_stage, req, energy_col, all_nutrients
                    )
                    st.session_state.diet = diet
                    st.session_state.total_cost = total_cost
                    st.session_state.nutritional_values = nutritional_values
                    st.session_state.compliance_data = compliance_data
                    st.session_state.recommendations = recommendations

                    # Display the updated composition to confirm changes
                    st.write("### Composición Actualizada")
                    st.dataframe(filtered_df[["Ingrediente", "Costo", energy_col, "PB", "Ca", "P", "Na", "Cl", "LYS", "MET"]])

        # Display results
        if st.session_state.diet and st.session_state.diet != {}:
            st.subheader("Dieta Optimizada")
            st.write("**Ingredientes seleccionados (%):**")
            for ingredient, amount in st.session_state.diet.items():
                st.write(f"{ingredient}: {amount:.2f}%")

            st.write(f"\n**Costo total (por 100 kg):** {st.session_state.total_cost:.2f}")

            # Display compliance with nutritional requirements
            st.subheader("Cumplimiento de Requerimientos Nutricionales")
            compliance_df = pd.DataFrame(st.session_state.compliance_data)
            st.table(compliance_df)

            if st.session_state.recommendations:
                st.subheader("Recomendaciones para Mejorar la Formulación")
                for rec in st.session_state.recommendations:
                    st.write(rec)
        else:
            st.error("No se pudo generar la dieta. Revisa los datos ingresados, ajusta los límites de inclusión o selecciona ingredientes con mayor contenido de nutrientes.")

    except Exception as e:
        st.error(f"Error al cargar el archivo Excel: {str(e)}")

else:
    st.write("Por favor, carga un archivo Excel con los ingredientes para continuar.")