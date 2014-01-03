{% extends 'common_synapses.cpp' %}

{% block maincode %}
    // This is only needed for the _debugmsg function below
    // USES_VARIABLES { _synaptic_pre }
	{% if pathway is defined %}
	vector<int32_t> *_spiking_synapses = {{pathway.name}}.queue->peek();
	const unsigned int _num_spiking_synapses = _spiking_synapses->size();
	{% endif %}
	for(unsigned int _spiking_synapse_idx=0;
		_spiking_synapse_idx<_num_spiking_synapses;
		_spiking_synapse_idx++)
	{
		const int32_t _idx = (*_spiking_synapses)[_spiking_synapse_idx];
		const int32_t _vectorisation_idx = _idx;
		{% for line in code_lines %}
		{{line}}
		{% endfor %}
	}
{% endblock %}

{% block extra_functions_cpp %}
void _debugmsg_{{codeobj_name}}()
{
	{% if owner is defined %}
	cout << "Number of synapses: " << {{_object__synaptic_pre}}.size() << endl;
	{% endif %}
}
{% endblock %}

{% block extra_functions_h %}
void _debugmsg_{{codeobj_name}}();
{% endblock %}

{% macro main_finalise() %}
_debugmsg_{{codeobj_name}}();
{% endmacro %}
