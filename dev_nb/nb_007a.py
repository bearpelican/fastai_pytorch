
        #################################################
        ### THIS FILE WAS AUTOGENERATED! DO NOT EDIT! ###
        #################################################
        # file to edit: dev_nb/007a_imdb_preparation.ipynb

from nb_007 import *

import pandas as pd, re, html, os

import warnings
warnings.filterwarnings("ignore", message="numpy.dtype size changed")
warnings.filterwarnings("ignore", message="numpy.ufunc size changed")

import spacy
from spacy.symbols import ORTH
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

BOS,FLD,UNK,PAD = 'xxbos','xxfld','xxunk','xxpad'
TK_UP,TK_REP,TK_WREP = 'xxup','xxrep','xxwrep'

def partition(a, sz):
    """splits iterables a in equal parts of size sz"""
    return [a[i:i+sz] for i in range(0, len(a), sz)]

def partition_by_cores(a, n_cpus):
    return partition(a, len(a)//n_cpus + 1)

def num_cpus():
    try:
        return len(os.sched_getaffinity(0))
    except AttributeError:
        return os.cpu_count()

class SpacyTokenizer():
    "Little wrapper around a spacy tokenizer"

    def __init__(self, lang):
        self.tok = spacy.load(lang)

    def tokenizer(self, t):
        return [t.text for t in self.tok.tokenizer(t)]

    def add_special_cases(self, toks):
        for w in toks:
            self.tok.tokenizer.add_special_case(w, [{ORTH: w}])

class Tokenizer():
    def __init__(self, tok_fn=SpacyTokenizer, lang:str='en', rules:Collection[Callable[[str],str]]=None,
                 special_cases:Collection[str]=None, n_cpus = None):
        self.tok_fn,self.lang,self.special_cases = tok_fn,lang,special_cases
        self.rules = rules if rules else []
        for rule in self.rules:
            if hasattr(rule, 'compile'): rule.compile()
        self.n_cpus = n_cpus or num_cpus()//2

    def __repr__(self):
        res = f'Tokenizer {self.tok_fn.__name__} in {self.lang} with the following rules:\n'
        for rule in self.rules: res += f' - {rule.__name__}\n'
        return res

    def proc_text(self, t, tok):
        for rule in self.rules: t = rule(t)
        return tok.tokenizer(t)

    def process_all_1thread(self, texts):
        tok = self.tok_fn(self.lang)
        if self.special_cases: tok.add_special_cases(self.special_cases)
        return [self.proc_text(t, tok) for t in texts]

    def process_all(self, texts):
        if self.n_cpus <= 1: return self.process_all_1thread(texts)
        with ProcessPoolExecutor(self.n_cpus) as e:
            return sum(e.map(self.process_all_1thread, partition_by_cores(texts, self.n_cpus)), [])

def sub_br(t):
    "Replaces the <br /> by \n"
    re_br = re.compile(r'<\s*br\s*/?>', re.IGNORECASE)
    return re_br.sub("\n", t)

def spec_add_spaces(t):
    return re.sub(r'([/#])', r' \1 ', t)

def rm_useless_spaces(t):
    return re.sub(' {2,}', ' ', t)

def replace_rep(t):
    def _replace_rep(m):
        c,cc = m.groups()
        return f' {TK_REP} {len(cc)+1} {c} '
    re_rep = re.compile(r'(\S)(\1{3,})')
    return re_rep.sub(_replace_rep, t)

def replace_wrep(t):
    def _replace_wrep(m):
        c,cc = m.groups()
        return f' {TK_WREP} {len(cc.split())+1} {c} '
    re_wrep = re.compile(r'(\b\w+\W+)(\1{3,})')
    return re_wrep.sub(_replace_wrep, t)

def deal_caps(t):
    res = []
    for s in re.findall(r'\w+|\W+', t):
        res += ([f' {TK_UP} ',s.lower()] if (s.isupper() and (len(s)>2)) else [s.lower()])
    return ''.join(res)

def fixup(x):
    re1 = re.compile(r'  +')
    x = x.replace('#39;', "'").replace('amp;', '&').replace('#146;', "'").replace(
        'nbsp;', ' ').replace('#36;', '$').replace('\\n', "\n").replace('quot;', "'").replace(
        '<br />', "\n").replace('\\"', '"').replace('<unk>',UNK).replace(' @.@ ','.').replace(
        ' @-@ ','-').replace('\\', ' \\ ')
    return re1.sub(' ', html.unescape(x))

rules = [fixup, replace_rep, replace_wrep, deal_caps, spec_add_spaces, rm_useless_spaces, sub_br]

def get_chunk_length(csv_name, chunksize):
    dfs = pd.read_csv(csv_name, header=None, chunksize=chunksize)
    l = 0
    for _ in dfs: l+=1
    return l

def get_total_length(csv_name, chunksize):
    dfs = pd.read_csv(csv_name, header=None, chunksize=chunksize)
    l = 0
    for df in dfs: l+=len(df)
    return l

def maybe_copy(old_fnames, new_fnames):
    os.makedirs(os.path.dirname(new_fnames[0]), exist_ok=True)
    for old_fname,new_fname in zip(old_fnames, new_fnames):
        if not os.path.isfile(new_fname) or os.path.getmtime(new_fname) < os.path.getmtime(old_fname):
            shutil.copyfile(old_fname, new_fname)

import hashlib

class Vocab():
    "Contains the correspondance between numbers and tokens and numericalizes"

    def __init__(self, path):
        self.itos = pickle.load(open(path/'itos.pkl', 'rb'))
        self.stoi = collections.defaultdict(int,{v:k for k,v in enumerate(self.itos)})

    def numericalize(self, t):
        return [self.stoi[w] for w in t]

    def textify(self, nums):
        return ' '.join([self.itos[i] for i in nums])

    @classmethod
    def create(cls, path, tokens, max_vocab, min_freq):
        freq = Counter(p for o in tokens for p in o)
        itos = [o for o,c in freq.most_common(max_vocab) if c > min_freq]
        itos.insert(0, PAD)
        if UNK in itos: itos.remove(UNK)
        itos.insert(0, UNK)
        pickle.dump(itos, open(path/'itos.pkl', 'wb'))
        h = hashlib.sha1(np.array(itos))
        with open(path/'numericalize.log','w') as f: f.write(h.hexdigest())
        return cls(path)

TextMtd = IntEnum('TextMtd', 'CSV TOK IDS')

import shutil

class TextDataset():
    "Put a train.csv and valid.csv files in a folder and this will take care of the rest."

    def __init__(self, path, tokenizer, vocab=None, max_vocab=30000, chunksize=10000, name='train',
                 min_freq=2, n_labels=1, create_mtd=TextMtd.CSV):
        self.path,self.tokenizer,self.max_vocab,self.min_freq = Path(path/'tmp'),tokenizer,max_vocab,min_freq
        self.chunksize,self.name,self.n_labels,self.create_mtd = chunksize,name,n_labels,create_mtd
        self.vocab=vocab
        os.makedirs(self.path, exist_ok=True)
        if not self.check_toks(): self.tokenize()
        if not self.check_ids():  self.numericalize()

        if self.vocab is None: self.vocab = Vocab(self.path)
        self.ids = np.load(self.path/f'{self.name}_ids.npy')
        self.labels = np.load(self.path/f'{self.name}_lbl.npy')

    def __getitem__(self, idx): return self.ids[idx],self.labels[idx]
    def __len__(self): return len(self.ids)

    def general_check(self, pre_files, post_files):
        "Checks that post_files exist and were modified after all the prefiles."
        if not np.all([os.path.isfile(fname) for fname in post_files]): return False
        for pre_file in pre_files:
            if os.path.getmtime(pre_file) > os.path.getmtime(post_files[0]): return False
        return True

    def check_ids(self):
        if self.create_mtd >= TextMtd.IDS: return True
        if not self.general_check([self.tok_files[0],self.id_files[1]], self.id_files): return False
        itos = pickle.load(open(self.id_files[1], 'rb'))
        h = hashlib.sha1(np.array(itos))
        with open(self.id_files[2]) as f:
            if h.hexdigest() != f.read() or len(itos) > self.max_vocab + 2: return False
        toks,ids = np.load(self.tok_files[0]),np.load(self.id_files[0])
        if len(toks) != len(ids): return False
        return True

    def check_toks(self):
        if self.create_mtd >= TextMtd.TOK: return True
        if not self.general_check([self.csv_file], self.tok_files): return False
        with open(self.tok_files[1]) as f:
            if repr(self.tokenizer) != f.read(): return False
        return True

    def tokenize(self):
        print(f'Tokenizing {self.name}. This might take a while so you should grab a coffee.')
        curr_len = get_chunk_length(self.csv_file, self.chunksize)
        dfs = pd.read_csv(self.csv_file, header=None, chunksize=self.chunksize)
        tokens,labels = [],[]
        for _ in progress_bar(range(curr_len), leave=False):
            df = next(dfs)
            lbls = df.iloc[:,range(self.n_labels)].values.astype(np.int64)
            texts = f'\n{BOS} {FLD} 1 ' + df[self.n_labels].astype(str)
            for i in range(self.n_labels+1, len(df.columns)):
                texts += f' {FLD} {i-n_lbls} ' + df[i].astype(str)
            toks = self.tokenizer.process_all(texts)
            tokens += toks
            labels += list(np.squeeze(lbls))
        np.save(self.tok_files[0], np.array(tokens))
        np.save(self.path/f'{self.name}_lbl.npy', np.array(labels))
        with open(self.tok_files[1],'w') as f: f.write(repr(self.tokenizer))

    def numericalize(self):
        print(f'Numericalizing {self.name}.')
        toks = np.load(self.tok_files[0])
        if self.vocab is None: self.vocab = Vocab.create(self.path, toks, self.max_vocab, self.min_freq)
        ids = np.array([self.vocab.numericalize(t) for t in toks])
        np.save(self.id_files[0], ids)

    def clear(self):
        files = [self.path/f'{self.name}_{suff}.npy' for suff in ['ids','tok','lbl']]
        files.append(self.path/f'{self.name}.csv')
        for file in files:
            if os.path.isfile(file): os.remove(file)

    @property
    def csv_file(self): return self.path/f'{self.name}.csv'
    @property
    def tok_files(self): return [self.path/f'{self.name}_tok.npy', self.path/'tokenize.log']
    @property
    def id_files(self):
        return [self.path/f'{self.name}_ids.npy', self.path/'itos.pkl', self.path/'numericalize.log']

    @classmethod
    def from_ids(cls, folder, name, id_suff='_ids', lbl_suff='_lbl', itos='itos.pkl', **kwargs):
        orig = [Path(folder/file) for file in [f'{name}{id_suff}.npy', f'{name}{lbl_suff}.npy', itos]]
        dest = [Path(folder)/'tmp'/file for file in [f'{name}_ids.npy', f'{name}_lbl.npy', 'itos.pkl']]
        maybe_copy(orig, dest)
        return cls(folder, None, name=name, create_mtd=TextMtd.IDS, **kwargs)

    @classmethod
    def from_tokens(cls, folder, name, tok_suff='_tok', lbl_suff='_lbl', **kwargs):
        orig = [Path(folder/file) for file in [f'{name}{tok_suff}.npy', f'{name}{lbl_suff}.npy']]
        dest = [Path(folder)/'tmp'/file for file in [f'{name}_tok.npy', f'{name}_lbl.npy']]
        maybe_copy(orig, dest)
        return cls(folder, None, name=name, create_mtd=TextMtd.TOK, **kwargs)

    @classmethod
    def from_csv(cls, folder, tokenizer, name, **kwargs):
        orig = [Path(folder)/f'{name}.csv']
        dest = [Path(folder)/'tmp'/f'{name}.csv']
        maybe_copy(orig, dest)
        return cls(folder, tokenizer, name=name, **kwargs)

    @classmethod
    def from_folder(cls, folder, tokenizer, name, classes=None, shuffle=True, **kwargs):
        path = Path(folder)/'tmp'
        os.makedirs(path, exist_ok=True)
        if classes is None: classes = [cls.name for cls in find_classes(Path(folder)/name)]
        texts,labels = [],[]
        for idx,label in enumerate(classes):
            for fname in (Path(folder)/name/label).glob('*.*'):
                texts.append(fname.open('r', encoding='utf8').read())
                labels.append(idx)
        texts,labels = np.array(texts),np.array(labels)
        if shuffle:
            idx = np.random.permutation(len(texts))
            texts,labels = texts[idx],labels[idx]
        df = pd.DataFrame({'text':texts, 'labels':labels}, columns=['labels','text'])
        if os.path.isfile(path/f'{name}.csv'):
            if get_total_length(path/f'{name}.csv', 10000) != len(df):
                df.to_csv(path/f'{name}.csv', index=False, header=False)
        else: df.to_csv(path/f'{name}.csv', index=False, header=False)
        txt_ds = cls(folder, tokenizer, name=name, **kwargs)
        txt_ds.classes = classes
        return txt_ds

def extract_kwargs(names, kwargs):
    new_kwargs = {}
    for arg_name in names:
        if arg_name in kwargs:
            arg_val = kwargs.pop(arg_name)
            new_kwargs[arg_name] = arg_val
    return new_kwargs, kwargs

class LanguageModelLoader():
    "Creates a dataloader with bptt slightly changing."
    def __init__(self, dataset, bs=64, bptt=70, backwards=False):
        self.dataset,self.bs,self.bptt,self.backwards = dataset,bs,bptt,backwards
        self.data = self.batchify(np.concatenate(dataset.ids))
        self.first,self.i,self.iter = True,0,0
        self.n = len(self.data)

    def __iter__(self):
        self.i,self.iter = 0,0
        while self.i < self.n-1 and self.iter<len(self):
            if self.first and self.i == 0: self.first,seq_len = False,self.bptt + 25
            else:
                bptt = self.bptt if np.random.random() < 0.95 else self.bptt / 2.
                seq_len = max(5, int(np.random.normal(bptt, 5)))
            res = self.get_batch(self.i, seq_len)
            self.i += seq_len
            self.iter += 1
            yield res

    def __len__(self): return (self.n-1) // self.bptt

    def batchify(self, data):
        nb = data.shape[0] // self.bs
        data = np.array(data[:nb*self.bs]).reshape(self.bs, -1).T
        if self.backwards: data=data[::-1]
        return LongTensor(data)

    def get_batch(self, i, seq_len):
        seq_len = min(seq_len, len(self.data) - 1 - i)
        return self.data[i:i+seq_len], self.data[i+1:i+1+seq_len].contiguous().view(-1)

def data_from_textids(path, train='train', valid='valid', test=None, lm=False, itos='itos.pkl', **kwargs):
    path=Path(path)
    txt_kwargs, kwargs = extract_kwargs(['max_vocab', 'chunksize', 'min_freq', 'n_labels', 'id_suff', 'lbl_suff'], kwargs)
    train_ds = TextDataset.from_ids(path, train, itos=itos, **txt_kwargs)
    datasets = [train_ds, TextDataset.from_ids(path, valid, itos=itos, **txt_kwargs)]
    if test: datasets.append(TextDataset.from_ids(path, test, itos=itos, **txt_kwargs))
    if not lm: return DataBunch.create(*datasets, path=path, **kwargs)
    dataloaders = [LanguageModelLoader(ds, **kwargs) for ds in datasets]
    return DataBunch(*dataloaders, path=path)

def data_from_texttokens(path, train='train', valid='valid', test=None, lm=False, vocab=None, **kwargs):
    path=Path(path)
    txt_kwargs, kwargs = extract_kwargs(['max_vocab', 'chunksize', 'min_freq', 'n_labels', 'tok_suff', 'lbl_suff'], kwargs)
    train_ds = TextDataset.from_tokens(path, train, vocab=vocab, **txt_kwargs)
    datasets = [train_ds, TextDataset.from_tokens(path, valid, vocab=train_ds.vocab, **txt_kwargs)]
    if test: datasets.append(TextDataset.from_tokens(path, test, vocab=train_ds.vocab, **txt_kwargs))
    if not lm: return DataBunch.create(*datasets, path=path, **kwargs)
    dataloaders = [LanguageModelLoader(ds, **kwargs) for ds in datasets]
    return DataBunch(*dataloaders, path=path)

def data_from_textcsv(path, tokenizer, train='train', valid='valid', test=None, lm=False, vocab=None, **kwargs):
    path=Path(path)
    txt_kwargs, kwargs = extract_kwargs(['max_vocab', 'chunksize', 'min_freq', 'n_labels'], kwargs)
    train_ds = TextDataset.from_csv(path, tokenizer, train, vocab=vocab, **txt_kwargs)
    datasets = [train_ds, TextDataset.from_csv(path, tokenizer, valid, vocab=train_ds.vocab, **txt_kwargs)]
    if test: datasets.append(TextDataset.from_csv(path, tokenizer, test, vocab=train_ds.vocab, **txt_kwargs))
    if not lm: return DataBunch.create(*datasets, path=path, **kwargs)
    dataloaders = [LanguageModelLoader(ds, **kwargs) for ds in datasets]
    return DataBunch(*dataloaders, path=path)

def data_from_textfolder(path, tokenizer, train='train', valid='valid', test=None, shuffle=True,
                         lm=False, vocab=None, **kwargs):
    path=Path(path)
    txt_kwargs, kwargs = extract_kwargs(['max_vocab', 'chunksize', 'min_freq', 'n_labels'], kwargs)
    train_ds = TextDataset.from_folder(path, tokenizer, train, shuffle=shuffle, vocab=vocab, **txt_kwargs)
    datasets = [train_ds, TextDataset.from_folder(path, tokenizer, valid, classes=train_ds.classes,
                                        shuffle=shuffle, vocab=train_ds.vocab, **txt_kwargs)]
    if test: datasets.append(TextDataset.from_folder(path, tokenizer, test, classes=train_ds.classes,
                                        shuffle=shuffle, vocab=train_ds.vocab, **txt_kwargs))
    if not lm: return DataBunch.create(*datasets, path=path, **kwargs)
    dataloaders = [LanguageModelLoader(ds, **kwargs) for ds in datasets]
    return DataBunch(*dataloaders, path=path)