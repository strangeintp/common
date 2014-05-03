import utility as U
import datetime as DT
import collections
import sys
import traceback


"""
An automated experimenter for running parameter sweeps/variations for discrete-
time-stepped simulations.  Outputs job results to console and file in .csv
format.

This class should not be instantiated.
Instead, it should be subclassed with one method override:
1) setupExperiment() -- see comments for that method below.

Depending on the scope of your getter and setter methods, in particular if they
are instance methods vice static class or module methods,
you may have to instantiate your main simulation class within the experiment
subclass' __init__() method, and move any run-unique simulation initialization
code to a reset() method within the simulation class.  That reset() method would
then be pointed to by the simInitFunc in Step 2 below.  So you are essentially
resetting the same object instance each time.

This addresses an order of declaration issue *if* you are using instance methods.
Since the setupExperiment method is run before the simulations are started, the
Python interpreter won't know your simulation class is supposed to have those methods
and will generate errors unless you declare an instance first.

E.g., showing a before and after case:

error-generating code:

class MySimClass(object):

    def __init__(self):
        initializeThis()
        initializeThat()

###  Different Module ###
class MyExperimentSubclass(Experiment):

    def __init__(self):
        super().__init__()

    def initializeSim(self):
        self.mySimInstance = MySimClass()

    def setupExperiment(self):
        ...
        self.simInitFunc = self.initializeSim()  # only called when a new simulation instance is run
        ...

        self.addParameter(mySimInstance.setSomeMySimParameter, [0, 1]) # <=== generates error; self.mySimInstance hasn't been instantiated yet

becomes:
class MySimClass(object):

    def __init__(self):
        pass # <=== you may still want to do non run-unique initialization here, but not for this example

    def reset(self):  # new method
        initializeThis()
        initializeThat()

###  Different Module ###
class MyExperimentSubclass(Experiment):

    def __init__(self):
        super().__init__()
        self.mySimInstance = MySimClass()  # Python Interpreter can now access instance methods

    # method commented out; no longer needed
    # def initializeSim(self):
        # self.mySimInstance = MySimClass()

    def setupExperiment(self):
        ...
        self.simInitFunc = self.mySimInstance.reset()  # called whenever a new simulation instance is run
        ...

        self.addParameter(mySimInstance.setSomeMySimParameter, [0, 1]) # <=== no error

Alternatively, use a singleton design pattern and access static class methods.


This automater will automatically calculate averages and standard deviations
over job repetitions for each job, for each of the output variables you've specified.
Modify the run() method if you need other metrics output for each job.

- Vince Kane, 29 Nov 2013
- modified 12 Feb 2014:
    - added parameter sweep value as a column for each job output
    - write consolidated job summary metrics to a summary output file
"""
class Experiment(object):

    def __init__(self):
        self.datetime = U.getTimeStampString()
        self.paramSetters = collections.OrderedDict()
        self.defaults = collections.OrderedDict()
        """ A dictionary of getter methods, accessed by a name for the variable """
        self.output_getters = collections.OrderedDict()
        """ A dictionary of string formats that tells the fileWriteOutput method how to format the output values"""
        self.output_formats = collections.OrderedDict()
        self.fileName = ""
        self.directory = "../output/"

    """
    Override this method in subclasses, with the sections completed.
    """
    def setupExperiment(self):
        """
        Section 1 - Experiment name and comments; describe the experiment.
        """
        self.Name = "Unnamed"  # this should be compatible with file names
        self.comments = "" # include a comment summarizing what the experiment is/does

        #######################################################################
        """
        Section 2 - Simulation behavior methods.
        Override the initiateSim, stepSim, and stopSim methods
        """

        #######################################################################
        """
        Section 3 - Add model parameters setters and defaults or variations.
        Note that this automater implements a full factorial design,
        so three parameters with a sweep of three values each generates 27 jobs.
        (And each job is repeated x times.)

        #template
        self.addParameter(setterMethod, values)
        if values is singular (non-iterable or list length==1),
        the parameter is set for all jobs in the experiment.
        #Examples:

        self.addParameter(setInitialPopulation, 100)
        # sets a default with setInitialPopulation(100)

        self.addParameter(setInitialPopulation, [100, 200])
        # includes setInitialPopulation in the full factorial design,
        # with parameter values of 100 and 200.
        """

        self.setupParameters()

        """
        Section 3.5 - Number of repetitions per job.
        """
        self.job_repetitions = 1
        #######################################################################
        """
        Section 4 - Add getter methods, names, and string formats so the automater
        can retrieve and record metrics from your simulation.

        #template
        self.addOutput(getterFunction, output_name, output_format)

        #Example:
        self.addOutput(getAveragePopulation, "Avg Pop.", "%8.4f")
        # getAveragePopulation() returns the average population of the sim run,
        # and the header "Avg Pop." will be written to the file
        """

    def addParameter(self, setterMethod, values):
        if not isinstance(values, list):
            self.defaults[setterMethod] = values
        elif len(values)==1:
            self.defaults[setterMethod] = values[0]
        else:
            self.paramSetters[setterMethod] = values

    def addOutput(self, getterFunction, output_name, output_format):
        self.output_getters[output_name] = getterFunction
        self.output_formats[output_name] = "," + output_format

    def setupFile(self):
        self.fileName = self.directory + self.Name + " " + self.datetime + ".csv"
        message = "Experiment " + self.Name
        message += "\n" + self.comments
        message += ".\nExperiment started %s\n"%self.datetime
        self.output(message)

    def checkParameters(self):
        if not self.paramSetters:
            self.output("There are no variants to combine.  A single job will run, with the defaults.")
            for setter in self.defaults:
                self.paramSetters[setter] = [self.defaults[setter]]

    def run(self):
        self.setupExperiment()
        self.setupOutputs()
        self.setupFile()
        self.checkParameters()
        self.setDefaults()
        self.design = self.full_factorial_design(self.paramSetters, job_id_name = "job_id")
        self.filewriteParameters()
        self.summary_avgs = collections.OrderedDict()
        self.summary_stds = collections.OrderedDict()
        try:
            self.simulate()
        except:
            traceback.print_exc()
            error = sys.exc_info()[0]
            self.output("Experiment halted on error: %s" % error)
        finally:
            ### close out
            self.output("\n######################################################")
            self.output("\nEXPERIMENT SUMMARY:  JOB AVERAGES")
            self.output("\n######################################################\n\n")
            job_output_header = ""
            for setter in self.paramSetters:
                job_output_header += ", " + setter.__name__
            for variable_name in self.output_getters:
                job_output_header += ", " + variable_name
            self.output(job_output_header)
            for job in self.design:
                self.outputFile.write("\n %d"%job["job_id"])
                self.fileWriteJobParameters(job)
                self.fileWriteOutputs(self.summary_avgs[job["job_id"]])
            self.output("\n######################################################")
            self.output("\nEXPERIMENT SUMMARY:  JOB STANDARD DEVIATIONS")
            self.output("\n######################################################\n\n")
            job_output_header = ""
            for setter in self.paramSetters:
                job_output_header += ", " + setter.__name__
            for variable_name in self.output_getters:
                job_output_header += ", " + variable_name
            self.output(job_output_header)
            for job in self.design:
                self.outputFile.write("\n %d"%job["job_id"])
                self.fileWriteJobParameters(job)
                self.fileWriteOutputs(self.summary_stds[job["job_id"]])
            self.output("\n######################################################")
            self.output("\nExperiment Completed %s"%U.getTimeStampString())
            self.output("\n######################################################\n\n")
            self.outputFile.close()

    def simulate(self):
        for job in self.design:
            self.setJobParameters(job)
            job_outputs = collections.OrderedDict()  # a dictionary accessed by output variable name
            # initialize empty lists to track repetition outputs for each output variable
            for output in self.output_getters:
                job_outputs[output] = []
            for i in range(self.job_repetitions):
                self.datetime = U.getTimeStampString()
                self.initiateSim()
                while not self.stopSim():
                    self.stepSim()
                outputs = self.getOutputs()
                for output in outputs:
                    job_outputs[output].append(outputs[output])
                self.outputFile.write("\n %s, %d"%(self.datetime, job["job_id"]))
                self.fileWriteJobParameters(job)
                self.fileWriteOutputs(outputs)

            # write statistics to file
            averages = collections.OrderedDict()
            stddevs = collections.OrderedDict()
            for variable in job_outputs:
                averages[variable] = U.mean(job_outputs[variable])
                stddevs[variable] = U.popStdDev(job_outputs[variable])
            self.summary_avgs[job["job_id"]] = averages
            self.summary_stds[job["job_id"]] = stddevs
            self.output("\naverages: ")
            self.fileWriteJobParameters(job)
            self.fileWriteOutputs(averages)
            self.output("\nstandard deviations: ")
            self.fileWriteJobParameters(job)
            self.fileWriteOutputs(stddevs)

    def getOutputs(self):
        outputs = collections.OrderedDict()
        for getter_name in self.output_getters:
            getter = self.output_getters[getter_name]
            outputs[getter_name] = getter()
        return outputs

    def fileWriteOutputs(self, outputs):
        message = ""
        for variable in outputs:
            message += self.output_formats[variable]%outputs[variable]
        self.output(message)

    def output(self, message):
        print(message)
        try:
            self.outputFile = open(self.fileName, 'a+')
            if self.outputFile != None:
                self.outputFile.write(message)
        except:
            print("Could not open output file for writing: %s" % sys.exc_info()[0])

    def filewriteParameters(self):
        self.output("\n######################################################")
        self.output("\nExperiment Defaults:")
        for setter in self.defaults:
            message = "\n"
            message += "%40s"%setter.__name__
            message += " :,  \t"
            value = self.defaults[setter]
            message += str(value)
            self.output(message)
        self.output("\nExperiment Parameter Variations:")
        for setter in self.paramSetters:
            message = "\n"
            message += "%40s"%setter.__name__
            message += " :,  \t"
            value = self.paramSetters[setter]
            message += str(value)
            self.output(message)
        self.output("\n######################################################")

    def setDefaults(self):
        for setter in self.defaults:
            # call the method with the value indexed by the method name in the defaults dictionary
            setter(self.defaults[setter])

    def setJobParameters(self, job):
        self.output("\n")
        self.output("*********************Job Settings*********************")
        job_output_header = "\n timestamp, job ID"
        for setter in self.paramSetters:
            v = setter(job[setter])
            self.output("\n%40s"%setter.__name__ + " :\t,%s"%str(v))
            job_output_header += ", " + setter.__name__
        for variable_name in self.output_getters:
            job_output_header += ", " + variable_name
        self.output(job_output_header)

    def fileWriteJobParameters(self, job):
        for setter in self.paramSetters:
            v = setter(job[setter])
            self.output(", %20s"%str(v))

    def full_factorial_design(self, parameters, job_id_name = "job_id"):
    # Vince Kane note:  function provided by:
    # *** Library for experiment designs generation ***
    #
    # Copyright 2013 Przemyslaw Szufel & Bogumil Kaminski
    # {pszufe, bkamins}@sgh.waw.pl
        if not isinstance(parameters, collections.OrderedDict):
            raise Exception("parameters must be OrderedDict")

        counter = [0] * len(parameters)
        maxcounter = []

        for dimension in parameters:
            if not isinstance(parameters[dimension], list):
                raise Exception("dimension must be a list")
            if dimension == job_id_name:
                raise Exception("dimension name equal to job_id_name")
            maxcounter.append(len(parameters[dimension]))
        result = []
        go = True
        job_id = 0
        while go:
            job_id += 1
            job = collections.OrderedDict()
            i = 0
            for dimension in parameters:
                job[dimension] = parameters[dimension][counter[i]]
                i += 1
            job[job_id_name] = job_id
            result.append(job)
            for i in range(len(parameters) - 1, -1, -1):
                counter[i] += 1
                if counter[i] == maxcounter[i]:
                    counter[i] = 0
                    if (i == 0):
                        go = False
                else:
                    break
        return result


