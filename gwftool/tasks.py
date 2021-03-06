
from .workflow_io import GalaxyWorkflow

class GalaxyWorkflowTask:
    """
    Instance of a Galaxy Workflow to be run
    """
    def __init__(self, engine, workflow, inputs=None, parameters=None, tags=None, step_tags=None):

        if not isinstance(workflow, GalaxyWorkflow):
            raise Exception("Need galaxy workflow")
        self.engine = engine
        self.workflow = workflow
        self.inputs = inputs
        self.parameters = parameters
        self.tags = tags
        self.step_tags = step_tags

    def is_valid(self):
        valid = True

        workflow_data = self.workflow.to_dict()
        outputs = {}
        for step in workflow_data['steps'].values():
            if 'post_job_actions' in step and len(step['post_job_actions']):
                for act in step['post_job_actions'].values():
                    if act['action_type'] == 'RenameDatasetAction':
                        new_name = act["action_arguments"]["newname"]
                        old_name = act["output_name"]
                        outputs[new_name] = GalaxyTargetFuture(
                            step_id=step['id'],
                            output_name=old_name
                        )

        for step in workflow_data['steps'].values():
            if step['type'] == 'data_input':
                name = step['inputs'][0]['name']
                if name not in self.inputs:
                    #raise CompileException("Missing input: %s" % (name))
                    valid = False
        return valid

    def get_inputs(self):
        out = {}
        for k, v in self.inputs.items():
            if isinstance(v, Target):
                out[k] = v
            else:
                logging.error("Unknown Input Type: %s" % (k))
        return out

    @staticmethod
    def from_dict(data, engine=None):
        request = {}
        for k, v in data['inputs'].items():
            if isinstance(v, dict) and 'uuid' in v:
                request[k] = Target(uuid=v['uuid'])
            else:
                request[k] = v
        if engine is None:
            engine = engine_from_dict(data['engine'])
        return GalaxyWorkflowTask(
            engine=engine, workflow=GalaxyWorkflow(data['workflow']),
            inputs=request, parameters=data.get('parameters', None),
            tags=data.get('tags', None), step_tags=data.get('step_tags', None)
        )

    def to_dict(self):
        return {
            'task_type' : 'GalaxyWorkflow',
            'engine' : self.engine.to_dict(),
            'workflow' : self.workflow.to_dict(),
            'inputs' : self.inputs,
            'parameters' : self.parameters,
            'tags' : self.tags,
            'step_tags' : self.step_tags
            #'outputs' : self.get_output_data(),
        }

    def get_workflow_request(self, uuid_ldda_map={}):
        #FIXME: This code is just copy pasted at the moment
        #need to integrate properly
        dsmap = {}
        parameters = {}
        out = {}
        workflow_data = self.workflow.to_dict()
        for k, v in self.inputs.items():
            if isinstance(v, Target):
                if k in workflow_data['steps']:
                    out[k] = {'src':'uuid', 'id' : v.uuid}
                else:
                    found = False
                    for step_id, step in workflow_data['steps'].items():
                        label = step['uuid']
                        if step['type'] == 'data_input':
                            if step['inputs'][0]['name'] == k:
                                if v.uuid in uuid_ldda_map:
                                    dsmap[label] = {'src':'ldda', 'id' : uuid_ldda_map[v.uuid]}
                                else:
                                    dsmap[label] = {'src':'uuid', 'id' : v.uuid}
            else:
                pass
        if self.parameters is not None:
            for k,v in self.parameters.items():
                if k in workflow_data['steps']:
                    out[k] == v
                else:
                    found = False
                    for step_id, step in workflow_data['steps'].items():
                        label = step['uuid']
                        if step['type'] == 'tool':
                            if step['annotation'] == k:
                                parameters[label] = v

        #TAGS
        if self.tags is not None or self.step_tags is not None:
            for step, step_info in workflow_data['steps'].items():
                step_id = step_info['uuid']
                if step_info['type'] == "tool":
                    step_name = None
                    if self.step_tags is not None:
                        if step_info['label'] in self.step_tags:
                            step_name = step_info['label']
                        if step_info['annotation'] in self.step_tags:
                            step_name = step_info['annotation']
                        if step_info['uuid'] in self.step_tags:
                            step_name = step_info['uuid']
                    tags = []
                    if self.tags is not None:
                        tags += self.tags

                    pja_map = {}
                    for i, output in enumerate(step_info['outputs']):
                        output_name = output['name']
                        if step_name is not None and output_name in self.step_tags[step_name]:
                            cur_tags = tags + self.step_tags[step_name][output_name]
                        else:
                            cur_tags = tags
                        if len(cur_tags):
                            pja_map["RenameDatasetActionout_file%s" % (len(pja_map))] = {
                                "action_type" : "TagDatasetAction",
                                "output_name" : output_name,
                                "action_arguments" : {
                                    "tags" : ",".join(cur_tags)
                                },
                            }

                    if len(pja_map):
                        if step_id not in parameters:
                            parameters[step_id] = {} # json.loads(step_info['tool_state'])
                        parameters[step_id]["__POST_JOB_ACTIONS__"] = pja_map



        out['workflow_id'] = workflow_data['uuid']
        out['inputs'] = dsmap
        out['parameters'] = parameters
        out['inputs_by'] = "step_uuid"
        return out

