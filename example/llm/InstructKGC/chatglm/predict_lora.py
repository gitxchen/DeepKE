import torch
import json
from modeling_chatglm import ChatGLMForConditionalGeneration
from tokenization_chatglm import ChatGLMTokenizer
from peft import get_peft_model, LoraConfig, TaskType, PeftModel
from tqdm import tqdm
import time
import os
import argparse


def set_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--test_path', default='data/test.json', type=str, help='')
    parser.add_argument('--device', default='0', type=str, help='')
    parser.add_argument('--model_dir',
                        default="/data/model", type=str,
                        help='')
    parser.add_argument('--max_len', type=int, default=768, help='')
    parser.add_argument('--max_src_len', type=int, default=450, help='')
    parser.add_argument('--prompt_text', type=str,
                        default="你现在是一个信息抽取模型，请你帮我抽取出关系内容为\"性能故障\", \"部件故障\", \"组成\"和 \"检测工具\"的相关三元组，三元组内部用\"_\"连接，三元组之间用\\n分割。文本：",
                        help='')
    return parser.parse_args()


def main():
    args = set_args()
    model = ChatGLMForConditionalGeneration.from_pretrained(args.model_dir)
    tokenizer = ChatGLMTokenizer.from_pretrained(args.model_dir)
    model.eval()
    model.half().to("cuda:{}".format(args.device))
    model.eval()
    save_data = []
    f1 = 0.0
    max_tgt_len = args.max_len - args.max_src_len - 3
    s_time = time.time()
    with open(args.test_path, "r", encoding="utf-8") as fh:
        for i, line in enumerate(tqdm(fh, desc="iter")):
            with torch.no_grad():
                sample = json.loads(line.strip())
                print(sample)
                src_tokens = tokenizer.tokenize(sample["input"])
                prompt_tokens = tokenizer.tokenize(sample["instruction"])

                if len(src_tokens) > args.max_src_len - len(prompt_tokens):
                    src_tokens = src_tokens[:args.max_src_len - len(prompt_tokens)]

                tokens = prompt_tokens + src_tokens + ["[gMASK]", "<sop>"]
                input_ids = tokenizer.convert_tokens_to_ids(tokens)

                input_ids = torch.tensor([input_ids]).to("cuda:{}".format(args.device))
                generation_kwargs = {
                    "min_length": 5,
                    "max_new_tokens": max_tgt_len,
                    "top_p": 0.7,
                    "temperature": 0.95,
                    "do_sample": False,
                    "num_return_sequences": 1,
                }
                response = model.generate_one(input_ids, **generation_kwargs)
                res = []
                for i_r in range(generation_kwargs["num_return_sequences"]):
                    outputs = response.tolist()[i_r][input_ids.shape[1]:]
                    r = tokenizer.decode(outputs).replace("<eop>", "")
                    res.append(r)
                save_data.append(
                    {"id":sample["id"],"cata":sample["cate"],"instruction":sample["instruction"],"input": sample["input"],"output": res[0]})

    e_time = time.time()
    print("总耗时：{}s".format(e_time - s_time))
    save_path = os.path.join(args.model_dir, "result.json")
    fin = open(save_path, "w", encoding="utf-8")
    json.dump(save_data, fin, ensure_ascii=False, indent=4)
    fin.close()


if __name__ == '__main__':
    main()