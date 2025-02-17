# SubtaskAEvaluation.py Version 1.2 as of July 1, 2024
# Douglas W. Oard, oard@umd.edu

# Changes from Version 1.2:
# - Added some processing of Subject-Numeric Codes for Brown folder name metadata

# Changes from Version 1.1:
# - Replaced hardcoded full path names with a prefix that will be used for all files.
# - Added computation of confidence intervals
# - Added detail to terrier package installation comments
# - Fixed a bug that made the index number unchanging for the random index

import json
import os
import pytrec_eval # For this to work, you should pip install pytrec-eval-terrier, which requires a version of numpy before 2.0 (such as 1.26.4)
import pyterrier as pt # For this to work you should pip install python-terrier
import pandas as pd
import re
import PyPDF2
import shutil
import random
import math

import GptSncExpansionTrainColbert

def readExperimentControlFile(fileName):
    with open(fileName) as ecfFile:
        ecf = json.load(ecfFile)
    return ecf

def getSushiFolders(dir):
    text = {}
    for box in os.listdir(dir):
        print(f'Reading SUSHI collection box {box}')
        text[box] = {}
        for folder in os.listdir(os.path.join(dir,box)):
            text[box][folder] = 'test'
    return text

def trainRandomModel(trainingDoucments): # This simple index identifies the top 1000 folders, in random order
    global prefix
    global seq
    dir = prefix + 'sushi-files/'
    folders = {}
    for box in os.listdir(dir):
        for folder in os.listdir(os.path.join(dir, box)):
            folders[folder] = []
            for file in os.listdir(os.path.join(dir, box, folder)):
                folders[folder].append(file)
    seq += 1
    index = list(folders.keys())
    random.shuffle(index)
    return index[0:1000]

def translateNaraFolderLabel (naraLabel, sncExpansion, sushiFile, sushiFolder):
    if naraLabel != 'nan':
        start = naraLabel.find('(')  # Strip part markings
        if start != -1:
            naraLabel = naraLabel[:start]
        naraLabel = naraLabel.replace('BRAZ-A0', 'BRAZ-A 0')  # Fix formatting error
        naraLabel = naraLabel.replace('BRAZ-E0', 'BRAZ-E 0')  # Fix formatting error
        naraLabelElements = naraLabel.split()
        if len(naraLabelElements) in [3, 4]:
            if len(naraLabelElements) == 3:
                naraSnc = naraLabelElements[0]
            else:
                naraSnc = ' '.join(naraLabelElements[0:2])
            naraCountryCode = naraLabelElements[-2]
            naraDate = naraLabelElements[-1]
            #                print(f'parsed {naraLabel} to {naraSnc} // {naraCountryCode} // {naraDate}')
            if naraSnc in sncExpansion['SNC'].tolist():
                label1965 = str(sncExpansion.loc[sncExpansion['SNC'] == naraSnc, 1965].iloc[0])
                label1963 = str(sncExpansion.loc[sncExpansion['SNC'] == naraSnc, 1963].iloc[0])
                if label1965 != 'nan':
                    label = label1965
                elif label1963 != 'nan':
                    label = label1963
                else:
                    print(f'Unable to translate {naraSnc} for file {sushiFile} in folder {sushiFolder}')
                    label = naraSnc
            else:
                print(f'No expansion for {naraSnc}')
                label = naraSnc
        else:
            print(f"NARA Folder Title doesn't have four parts: {naraLabel}")
            label = 'Bad NARA Folder Title'
            naraSnc = naraLabelElements[0]
            naraCountryCode = 'Unknown'
            naraDate = 'Unknown'
    return naraSnc, label, naraCountryCode, naraDate

def translateBrownFolderLabel(brownLabel, sncExpansion, sushiFile, sushiFolder):
    label = ''
    cleanLabel = brownLabel.replace('_', ' ')
#    if len(cleanLabel)<20:
#        print(cleanLabel)
#    label = re.sub(r'(^[A-Z][A-Za-z]{1,3})(\s?)([(\d{1,2}\s\d{1,2)(\d{1,2}\-\d{1,2})(\d{1.2})(\s)])(\s?)(.*)', r'\1#\3#\5', cleanLabel)
    datePattern = re.compile(r'(^.*)([\s\-])(1?\d[\-\/][123]?\d[\-\/]?[67]\d)(.*$)')
    match = datePattern.search(cleanLabel)
    if match:
        before = match.group(1).strip()
        date = match.group(3).strip()
        if date[-2] in ['6', '7'] and date[-3] not in ['-', '/', ' ']:
            date = date[0:-2] + '-' + date[-2:]
#        else:
#            print(f'Date: {date} Date[-2]: {date[-2]}')
        after = match.group(4).strip()
    else:
        before = cleanLabel
        date = ''
        after = ''

    catPattern = re.compile(r'(^[A-Z][A-Za-z]{0,4})(.*)$')
    match = catPattern.search(before)
    if match: # and before!='Unknown' and 'Untitled' not in before:
        category = match.group(1).strip()
        subcats = match.group(2).strip().strip('-').strip()
    if not match or len(category)>4:
        category = ''
        subcats = ''
        label = before

    snc1Pattern = re.compile(r'(^\d\d?)(.*)')
    match = snc1Pattern.search(subcats)
    if match:
        level1 = match.group(1).strip()
        remainder = match.group(2).strip()
    else:
        level1 = ''
        remainder = subcats

    snc2Pattern = re.compile(r'(\-)(\d\d?)(.*)')
    match = snc2Pattern.search(remainder)
    if match:
        level2 = match.group(2).strip()
        remainder = match.group(3).strip()+' '+after
        remainder = remainder.strip()
    else:
        level2 = ''
        remainder = remainder + ' ' + after
        remainder = remainder.strip().strip('-').strip()

    if category != '':
        if level1 != '':
            if level2 != '':
                brownSnc = category.upper() + ' ' + level1 + '-' + level2
            else:
                brownSnc = category.upper() + ' ' + level1
        else:
            brownSnc = category.upper()
    else:
         brownSnc = 'Unknown'

    if brownSnc in sncExpansion['SNC'].tolist():
        label1965 = str(sncExpansion.loc[sncExpansion['SNC'] == brownSnc, 1965].iloc[0])
        label1963 = str(sncExpansion.loc[sncExpansion['SNC'] == brownSnc, 1963].iloc[0])
        if label1965 != 'nan':
            label2 = label1965
        elif label1963 != 'nan':
            label2 = label1963
        else:
#            print(f'Unable to translate {brownSnc} for file {sushiFile} in folder {sushiFolder}')
            label2 = brownSnc
    else:
#        print(f'No expansion for {brownSnc}')
        label2 = 'Unknown'

    if label == '':
        if label2 == 'Unknown':
            label = remainder
        else:
            label = label2

#    if len (cleanLabel) < 2000:
#        print(f'{cleanLabel:55}   Brown SNC: {brownSnc:10}   Date: {date:15}   Label: {label:4} ')

    if len(cleanLabel)<20:
        return brownSnc, label
    else:
        return brownSnc, cleanLabel

def replace_straight_quotes(text):
    if '\u201c' in text or '\u201d' in text: print('Found curly quotes')
    text = text.replace('"', '\u201c')  # Replace opening double quotes
    text = text.replace('"', '\u201d')  # Replace closing double quotes
    text = text.replace("'", '\u2018')  # Replace opening single quotes
    text = text.replace("'", '\u2019')  # Replace closing single quotes
    return text

def createTrainingSet(trainingDocs, searchFields):
    noShortOcr = False  # Set to true if you want to replace OCR text that is nearly empty with the document title
    global prefix
    global seq  # Used to control creation of a separate index for each training set
    global unix  # Used to accommodate Terrier's use of var for indexes with Unix
    trainingSet = []
    known = {}

    # Read the Sushi Medadata and SNC excel files
    try:
        xls = pd.ExcelFile(prefix + 'SubtaskACollectionMetadataV1.1.xlsx')
        fileMetadata = xls.parse(xls.sheet_names[0])
        xls = pd.ExcelFile(prefix + 'SncTranslationV1.2.xlsx')
        sncExpansion = xls.parse(xls.sheet_names[0])
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        exit(-1)

    # Build the data structure that Terrier will index (list of dicts, one per indexed item)
    for trainingDoc in trainingDocs:

        # Read the box/folder/file directory structure
        sushiFile = trainingDoc[
                    -10:]  # This extracts the file name and ignores the box and folder labels which we will get from the metadata
        file = sushiFile
        folder = str(fileMetadata.loc[fileMetadata['Sushi File'] == sushiFile, 'Sushi Folder'].iloc[0])
        box = str(fileMetadata.loc[fileMetadata['Sushi File'] == sushiFile, 'Sushi Box'].iloc[0])

        # Construct the best available folder label (either by SNC lookup or by using the folder label text)
        naraLabel = str(fileMetadata.loc[fileMetadata['Sushi File'] == sushiFile, 'NARA Folder Name'].iloc[0])
        brownLabel = str(fileMetadata.loc[fileMetadata['Sushi File'] == sushiFile, 'Brown Folder Name'].iloc[0])
        if naraLabel != 'nan':
            snc, label, naraCountryCode, naraDate = translateNaraFolderLabel(naraLabel, sncExpansion, file, folder)
        else:
            if brownLabel != 'nan':
                snc, label = translateBrownFolderLabel(brownLabel, sncExpansion, file, folder)
            else:
                print(f'Missing both NARA and Brown folder labels for file {file} in folder {folder}')
                label = 'No NARA or Brown Folder Title'
                snc = 'unknown'
        #        print(f'File {file} Folder {folder} has expanded label {label}')

        # Construct the best available title (either Brown, or trimmed NARA)
        brownTitle = str(fileMetadata.loc[fileMetadata['Sushi File'] == sushiFile, 'Brown Title'].iloc[0])
        naraTitle = str(fileMetadata.loc[fileMetadata['Sushi File'] == sushiFile, 'NARA Title'].iloc[0])
        if brownTitle != 'nan':
            title = brownTitle
        else:
            start = naraTitle.find('Concerning')
            if start != -1:
                naraTitle = naraTitle[start + 11:]
            end1 = naraTitle.rfind(':')
            end2 = naraTitle.rfind('(')
            end = min(end1, end2)
            if end != -1:
                naraTitle = naraTitle[:end]
            title = naraTitle

        # Extract OCR text from the PDF file
        f = open(prefix + 'sushi-files/' + box + '/' + folder + '/' + file, 'rb')
        reader = PyPDF2.PdfReader(f)
        pages = len(reader.pages)
        maxPages = 1  # Increase this number if you want to index more of the OCR text
        fulltext = ''
        for i in range(min(pages, maxPages)):
            page = reader.pages[i]
            text = page.extract_text().replace('\n', ' ')
            fulltext = fulltext + text
        ocr = fulltext

        # Optionally replace any hopelessly short OCR with the document title
        if noShortOcr and len(ocr) < 5:
            print(f'Replaced OCR: //{ocr}// with Title //{title}//')
            ocr = title

        # Read the GPT Summary
        f = open(prefix + 'summary/prompt-1/' + box + '/' + folder + '/' + file.replace('.pdf', '.txt'), 'r',
                 encoding='utf8')
        summary = f.read()
        summary = replace_straight_quotes(summary)
        #        print(f'{box}/{folder}/{file}: {len(summary.split())} words')

        if snc in known:
            known[snc]['title'].append(title)
            known[snc]['ocr'].append(ocr)
            known[snc]['summary'].append(summary)
        else:
            known[snc] = {}
            known[snc]['title'] = [title]
            known[snc]['ocr'] = [ocr]
            known[snc]['summary'] = [summary]

        trainingSet.append(
            {'docno': file, 'folder': folder, 'box': box, 'title': title, 'ocr': ocr, 'folderlabel': label,
             'summary': summary})

    for snc in known:
        print(snc, known[snc]['title'])

    dir = prefix+'sushi-files/'
    good = 0
    bad = 0
    nochange = 0
    sum = 0
    expanding = True
    for box in os.listdir(dir):
        if not box.startswith('.'):
            #        print(f'Reading SUSHI collection box {box}')
            for folder in os.listdir(os.path.join(dir, box)):
                if not folder.startswith('.') and folder != 'N160894698':
                    if folder == 'N160894698':
                        print(f"Folder name: {folder}")
                    naraLabel = str(
                        fileMetadata.loc[fileMetadata['Sushi Folder'] == folder, 'NARA Folder Name'].iloc[0])
                    brownLabel = str(
                        fileMetadata.loc[fileMetadata['Sushi Folder'] == folder, 'Brown Folder Name'].iloc[0])
                    if naraLabel != 'nan':
                        snc, label, naraCountryCode, naraDate = translateNaraFolderLabel(naraLabel, sncExpansion,
                                                                                         'dummy', folder)
                    else:
                        if brownLabel != 'nan':
                            snc, label = translateBrownFolderLabel(brownLabel, sncExpansion, 'dummy', folder)
                        else:
                            print(f'Missing both NARA and Brown folder labels for a file in folder {folder}')
                            label = 'No NARA or Brown Folder Title'
                            snc = 'unknown'
                    if snc in known:
                        stop = False
                        for item in trainingSet:
                            if item['folder'] == folder:
                                #                        print(f'Already indexed a document in {box}/{folder}/')
                                nochange += 1
                                stop = True
                        if not stop:
                            print(
                                f'Folder {box}/{folder}/ has known SNC {snc} with {len(known[snc]["title"])} sample(s)')
                            good += 1
                            sum += len(known[snc]['title'])
                            if expanding:
                                print('Expanded')
                                trainingSet.append({'docno': 'expanded', 'folder': folder, 'box': box,
                                                    'title': " ".join(known[snc]['title']),
                                                    'ocr': " ".join(known[snc]['ocr']), 'folderlabel': label,
                                                    'summary': " ".join(known[snc]['summary'])})
                    else:
                        print(f'Unknown SNC {snc}')
                        bad += 1
    print(
        f'Expansion possible: {good} with average of {sum / good:.1f} samples, No expansion needed: {nochange}. No expansion possible: {bad}, Distinct: {len(known)}')

    return trainingSet

def trainColbertModel(trainingDocs, searchFields):
    trainingSet = createTrainingSet(trainingDocs, searchFields)

    GptSncExpansionTrainColbert.test_colbert(trainingSet)

def trainTerrierModel(trainingDocs, searchFields):

    trainingSet = createTrainingSet(trainingDocs, searchFields)

    # Create the Terrier index for this training set and then return a Terrier retriever for that index
    seq += 1 # We create one Terrier index per training set
    indexDir = prefix + 'terrierindex/'+str(seq) # Be careful here -- this directory and all its contents will be deleted!
    if 'index' in indexDir and os.path.isdir(indexDir):
        print(f'Deleting prior index {indexDir}')
        shutil.rmtree(indexDir) # This is required because Terrier fails to close its index on completion
#    if not pt.java.started(): pt.init()
    indexer = pt.IterDictIndexer(indexDir, meta={'docno': 20, 'folder':20, 'box': 20, 'title':16384, 'ocr':16384, 'folderlabel': 1024}, meta_reverse=['docno', 'folder', 'box'], overwrite=True)
    indexref = indexer.index(trainingSet, fields=searchFields)
    index = pt.IndexFactory.of(indexref)
    BM25 = pt.BatchRetrieve(index, wmodel="BM25", metadata=['docno', 'folder', 'box'], num_results=1000)
    return BM25

def trainModel(trainingDocuments, searchFields):
    global seq
    global model
    print(f'Training Called, preparing index for experiment set {seq+1}')
    if model == 'random':
        return trainRandomModel(trainingDocuments)
    elif model == 'terrier':
        return trainTerrierModel(trainingDocuments, searchFields)
    else:
        return trainColbertModel(trainingDocuments, searchFields)

def randomSearch(query, index): # This search ignores the query and returns the same ranked list of folders every time
    return index

def terrierSearch(query, engine):
#    if not pt.java.started(): pt.init()
    query = re.sub(r'[^a-zA-Z0-9\s]', '', query) # Terries fails if punctuation is found in a query
    result = engine.search(query)
    rankedList = result['folder']
    rankedList.drop_duplicates(inplace=True)
    return rankedList.tolist()

def search(query, index):
    global model
    if model=='random':
        return randomSearch(query, index)
    elif model == 'terrier':
        return terrierSearch(query, index)
    else:
        return GptSncExpansionTrainColbert.colbert_search(query)

def generateSearchResults(ecf, searchFields):
    results = []
    i = 0
    for experimentSet in ecf['ExperimentSets']:
        index = trainModel(experimentSet['TrainingDocuments'], searchFields)
        topics = list(experimentSet['Topics'].keys())
        for j in range(len(topics)):
            results.append({})
            results[i]['Id'] = topics[j]
            query = experimentSet['Topics'][topics[j]]['TITLE']
            rankedFolderList = search(query, index)
            results[i]['RankedList'] = rankedFolderList
            i+=1
    return results

def writeSearchResults(fileName, results, runName):
    with open(fileName, 'w') as f:
        for topic in results:
            for i in range(len(topic['RankedList'])):
                print(f'{topic["Id"]}\t{topic["RankedList"][i]}\t{i+1}\t{1/(i+1):.4f}\t{runName}', file=f)
    f.close()

def createFolderToBoxMap(dir):
    boxMap = {}
    for box in os.listdir(dir):
        for folder in os.listdir(os.path.join(dir,box)):
            if folder in boxMap:
                print(f'Duplicate folder {folder} in boxes {box} and {boxMap[folder]}')
            boxMap[folder] = box
    return boxMap

def makeBoxRun(folderRun):
    global prefix
    boxMap = createFolderToBoxMap(prefix+'sushi-files/')
    boxRun = {}
    for topicId in folderRun:
        boxRun[topicId]={}
        for folder in folderRun[topicId]:
            if boxMap[folder] not in boxRun[topicId]:
               boxRun[topicId][boxMap[folder]] = folderRun[topicId][folder]
    return boxRun

def stats(results, measure):
    sum=0
    squaredev=0
    n = len(results)
    for topic in results:
        sum += results[topic][measure]
    mean = sum / n
    for topic in results:
        squaredev += (results[topic][measure]-mean)**2
    variance = squaredev / (n-1)
    conf = 1.96 * math.sqrt(variance) / math.sqrt(n)
    return mean, conf

def evaluateSearchResults(runFileName, folderQrelsFileName, boxQrelsFileName):
#    print(pytrec_eval.supported_measures)
    measures = {'ndcg_cut', 'map', 'recip_rank', 'success'} # Generic measures for configuring a pytrec_eval evaluator
    measureNames = {'ndcg_cut_5': 'NDCG@5', 'map': '   MAP', 'recip_rank': '   MRR', 'success_1': '   S@1'} # Spedific measures for printing in pytrec_eval results

    with open(runFileName) as runFile, open(folderQrelsFileName) as folderQrelsFile, open(boxQrelsFileName) as boxQrelsFile:
        folderRun = {}
        for line in runFile:
            topicId, folderId, rank, score, runName = line.split('\t')
            if topicId not in folderRun:
                folderRun[topicId] = {}
            folderRun[topicId][folderId] = float(score)
        boxRun = makeBoxRun(folderRun)
        folderQrels = {}
        for line in folderQrelsFile:
            topicId, unused, folderId, relevanceLevel = line.split('\t')
            if topicId not in folderQrels:
                folderQrels[topicId] = {}
            folderQrels[topicId][folderId] = int(relevanceLevel.strip())  # this deletes the \n at end of line
        folderEvaluator = pytrec_eval.RelevanceEvaluator(folderQrels, measures)
        folderTopicResults = folderEvaluator.evaluate(folderRun)  # replace run with folderQrels to see perfect evaluation measures

        boxQrels = {}
        for line in boxQrelsFile:
            topicId, unused, folderId, relevanceLevel = line.split('\t')
            if topicId not in boxQrels:
                boxQrels[topicId] = {}
            if folderId in boxQrels[topicId]:
                boxQrels[topicId][folderId] = max(boxQrels[topicId][folderId],int(relevanceLevel.strip()))  # strip() deletes the \n at end of line
            else:
                boxQrels[topicId][folderId] = int(relevanceLevel.strip())
        boxEvaluator = pytrec_eval.RelevanceEvaluator(boxQrels, measures)
        boxTopicResults = boxEvaluator.evaluate(boxRun) # replace run with qrels to see perfect evaluation measures

        pm='\u00B1'
        print(f'          Folder          Box')
        for measure in measureNames.keys():
            folderMean, folderConf = stats(folderTopicResults, measure)
            boxMean, boxConf = stats(boxTopicResults, measure)
            print(f'{measureNames[measure]}: {folderMean:.3f}{pm}{folderConf:.2f}    {boxMean:.3f}{pm}{boxConf:.2f}' )
        generateReadableResults('readableresults.txt', boxRun, boxQrels)

def generateReadableResults(filename, boxRun, boxQrels):
    f = open(prefix+filename, 'w')
    xls = pd.ExcelFile(prefix + 'SubtaskACollectionMetadataV1.1.xlsx')
    fileMetadata = xls.parse(xls.sheet_names[0])
    ecf = readExperimentControlFile(prefix+'Ntcir18SushiDryRunExperimentControlFileV1.1.json')
#    print(ecf["ExperimentSets"][0]["Topics"])
    j=0
    for topic in boxRun:
        if j<100:
#            print(f'Topic: {topic}    Query: {ecf["ExperimentSets"][0]["Topics"][topic]["TITLE"]}', file=f)
#        print(boxRun[topic])
            rankedList = list(boxRun[topic].keys())
            for i in range(min(5,len(rankedList))):
                naraBoxName = str(fileMetadata.loc[fileMetadata['Sushi Box'] == rankedList[i], 'NARA Box Name'].iloc[0])
                brownBoxName = str(fileMetadata.loc[fileMetadata['Sushi Box'] == rankedList[i], 'Brown Box Name'].iloc[0])
                print(f'Rank: {i+1},    Sushi Box: {rankedList[i]}    NARA Box: {naraBoxName}    Brown Box: {brownBoxName}', file=f)
        j+=1
        print('', file=f)
    f.close()

if __name__ == '__main__':
    # Set JAVA_HOME so that Terrier will work correctly
    os.environ["JAVA_HOME"] = "/Users/shashank/Research/java/jdk-22.0.1.jdk.amd/Contents/Home/" # Install Java if you don't already have it (tested with JDK 22) and then set this to where you have Java installed

    # Set global variables
    prefix = '/fs/clip-projects/archive_search/sushi/' # Absolute path for the sushi directory where all files and indexes will be.  Don't use relative paths; doing so alters terrier's behavior in a way that breaks this code.
    seq=0 # Controls index segments
    unix = False # Set to false for Windows, true for Unix.  This adapts the code to the locations where Terrier writes its index.
    model = 'colbert' # Set to 'random' for the random model or to 'terrier' for the Terrier model

    # Run the experiment
#    searchFields = ['title', 'ocr', 'folderlabel', 'summary'] # Used only with Terrier.  Edit this list to index fewer fields if desired
    searchFields = ['folderlabel']

    ecf = readExperimentControlFile(prefix+'Ntcir18SushiDryRunExperimentControlFileV1.1.json')
    results = generateSearchResults(ecf, searchFields)
    writeSearchResults(prefix+'Ntcir18SushiDryRunResultsV1.1.tsv', results, 'Baseline-0')
    evaluateSearchResults(prefix+'Ntcir18SushiDryRunResultsV1.1.tsv', prefix+'Ntcir18SushiDryRunFolderQrelsV1.1.tsv', prefix+'Ntcir18SushiDryRunBoxQrelsV1.1.tsv')